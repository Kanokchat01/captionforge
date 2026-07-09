"""
Primary caption generator: Gemini 2.5 Flash, two-stage pipeline per the
team's prompts.md design.

Stage 1: upload video, ask for a structured 10-section Scene Report
         (video + audio understood natively, no FFmpeg/Whisper needed).
Stage 2: text-only call using ONLY the Stage 1 report to generate the
         requested style captions as JSON. Cheaper/faster than a second
         video call, and forces grounding through the report's RISKS section.

Note: caption_clip() returns (captions, scene_report) as a tuple rather than
stashing scene_report on self — this class instance is shared across worker
threads in main.py's ThreadPoolExecutor, so storing per-call state on self
would race between concurrently-processing clips.
"""
import json
import re
import time

from google import genai
from google.genai import types

import config
from prompts import build_caption_generation_prompt, SCENE_ANALYSIS_PROMPT

# Gemini's own infra occasionally returns transient errors ("high demand,
# try again later" / 503 / 429 rate limits). A real test run hit this: all
# 3 clips failed on the very first attempt with zero retry. These are worth
# retrying briefly before giving up to a fallback caption.
MAX_API_RETRIES = 2
RETRY_BACKOFF_SECONDS = [3, 6]
RETRYABLE_MARKERS = ("503", "429", "unavailable", "rate limit", "resource_exhausted", "timeout", "deadline")
MAX_RETRY_DELAY_SECONDS = 25  # cap so one clip can't eat the whole run budget


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in RETRYABLE_MARKERS)


def _extract_retry_delay_seconds(exc: Exception):
    """Gemini's 429/RESOURCE_EXHAUSTED errors include a RetryInfo block with
    the server's own suggested wait (e.g. 'retryDelay': '16s') — a real test
    run at 8 concurrent clips hit the free tier's 5 requests/minute cap, and
    our old fixed 3s/6s backoff was far shorter than the ~16s the API
    actually asked for, so retries kept failing immediately. Prefer the
    server's number when we can parse it; fall back to the fixed schedule
    otherwise (e.g. for 503s, which don't carry a RetryInfo block)."""
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return None
    try:
        error_details = details.get("error", {}).get("details", [])
        for d in error_details:
            if isinstance(d, dict) and str(d.get("@type", "")).endswith("RetryInfo"):
                raw = str(d.get("retryDelay", "")).rstrip("s")
                return min(float(raw), MAX_RETRY_DELAY_SECONDS)
    except Exception:
        pass
    return None


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: pull the first {...} blob out of the response.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse JSON from Gemini response: {text[:300]}")


class SceneAnalysisFailed(Exception):
    """Raised when Gemini explicitly reports it could not analyze the clip
    (corrupted/blank/unreadable) rather than silently hallucinating."""
    pass


class GeminiCaptioner:
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("Missing GEMINI_API_KEY")
        self.model = model or config.GEMINI_MODEL
        self.client = genai.Client(api_key=self.api_key)

    def _generate_with_retry(self, **kwargs):
        """Wraps generate_content with a short bounded retry for transient
        infra errors (503/429/timeout-style). Non-retryable errors (bad
        request, auth, parsing) raise immediately on the first attempt."""
        last_exc = None
        for attempt in range(MAX_API_RETRIES + 1):
            try:
                return self.client.models.generate_content(**kwargs)
            except Exception as e:
                last_exc = e
                if attempt < MAX_API_RETRIES and _is_retryable(e):
                    server_delay = _extract_retry_delay_seconds(e)
                    delay = server_delay if server_delay is not None else RETRY_BACKOFF_SECONDS[attempt]
                    print(f"[retry] transient Gemini error (attempt {attempt + 1}/{MAX_API_RETRIES + 1}, "
                          f"waiting {delay:.0f}s): {e}")
                    time.sleep(delay)
                    continue
                raise
        raise last_exc

    def _upload_and_wait(self, video_path: str, max_wait_seconds: int):
        # Explicit mime_type instead of relying on the SDK's filename-based
        # guess: a real test with Google-Drive-hosted clips
        # (uc?export=download&id=...) hit "Unknown mime type" on every one
        # of them, because the downloaded local file has no .mp4 extension
        # for the SDK to sniff from. Since the whole pipeline's contract is
        # "video_url always points to a video clip", forcing video/mp4 here
        # makes the upload robust to whatever shape the URL takes, not just
        # the ones that happen to end in a recognizable file extension.
        video_file = self.client.files.upload(
            file=video_path,
            config=types.UploadFileConfig(mime_type="video/mp4"),
        )
        waited = 0
        while video_file.state.name == "PROCESSING" and waited < max_wait_seconds:
            time.sleep(3)
            waited += 3
            video_file = self.client.files.get(name=video_file.name)

        if video_file.state.name != "ACTIVE":
            try:
                self.client.files.delete(name=video_file.name)
            except Exception:
                pass
            raise RuntimeError(f"Video did not become ACTIVE in time (state={video_file.state.name})")

        return video_file

    def caption_clip(self, video_path: str, styles: list, max_wait_seconds: int = 90):
        """Runs the full 2-stage pipeline for one clip.
        Returns (captions: dict, scene_report: str)."""
        video_file = self._upload_and_wait(video_path, max_wait_seconds)

        try:
            # --- Stage 1: structured scene analysis (video + audio) ---
            analysis_resp = self._generate_with_retry(
                model=self.model,
                contents=[video_file, SCENE_ANALYSIS_PROMPT],
                config=types.GenerateContentConfig(temperature=0.4),
            )
            scene_report = (analysis_resp.text or "").strip()
        finally:
            try:
                self.client.files.delete(name=video_file.name)
            except Exception:
                pass

        if scene_report.upper().startswith("ANALYSIS FAILED"):
            raise SceneAnalysisFailed(scene_report)

        # --- Stage 2: caption generation, text-only, from the report ---
        prompt2 = build_caption_generation_prompt(scene_report, styles)
        gen_resp = self._generate_with_retry(
            model=self.model,
            contents=[prompt2],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.85,
            ),
        )

        captions = _extract_json(gen_resp.text)
        result = {s: str(captions.get(s, "")).strip() for s in styles}
        return result, scene_report
