"""
Alternate captioner: Fireworks-hosted vision model (MiniMax M3) over
extracted still frames, instead of Gemini's native video+audio call.

Why this exists: the team wanted to consolidate on Fireworks (already used
for Gemma polish/critique) instead of depending on Gemini for the primary
scene-understanding pass. Two things were verified before writing this:
  1. Fireworks' own chat completions docs/examples for MiniMax M3 only show
     `image_url` content parts — no documented `video_url`/raw-video input,
     so sending a whole video file to Fireworks is not a supported, reliable
     path today.
  2. Fireworks' Whisper/audio-transcription endpoints
     (audio-prod/audio-turbo.api.fireworks.ai) were confirmed discontinued
     as of 2026-06-10 (return 401 regardless of payload) — so there is no
     way to recover audio understanding on this path either.

Net effect: this path is frames-only, no audio. It trades away Gemini's
native audio understanding (speech/music/ambient sound) for running
entirely on Fireworks. Selected via config.CAPTION_PROVIDER=fireworks_vision
(default remains "gemini" — this path is opt-in, not the safe default).

Interface matches gemini_client.GeminiCaptioner exactly
(caption_clip(video_path, styles) -> (captions: dict, scene_report: str)) so
main.py only needs a small factory branch, not a rewrite.
"""
import base64
import json
import re
import subprocess
import tempfile
import time
import os

import requests

import config
from prompts import build_caption_generation_prompt, build_frame_scene_analysis_prompt

MAX_API_RETRIES = 2
RETRY_BACKOFF_SECONDS = [3, 6]
RETRYABLE_MARKERS = ("503", "429", "unavailable", "rate limit", "resource_exhausted", "timeout", "deadline", "502", "504")


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in RETRYABLE_MARKERS)


class SceneAnalysisFailed(Exception):
    """Raised when the model explicitly reports it could not analyze the
    frames (corrupted/blank/unreadable) rather than silently hallucinating."""
    pass


def _probe_duration_seconds(video_path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return max(float(out.stdout.strip()), 0.1)
    except (ValueError, AttributeError):
        return 10.0  # unknown duration fallback — still try to grab a few frames


def _extract_frames(video_path: str, max_frames: int, workdir: str):
    """Seeks to `max_frames` evenly-spaced timestamps and grabs one JPEG
    frame at each via ffmpeg. Returns a list of (timestamp_seconds, jpeg_bytes).
    Uses per-timestamp -ss seeking (accurate, one process per frame) rather
    than a single fps= filter pass — max_frames is small (default 8) so the
    extra process overhead is negligible and timestamps come out exact.

    Frames are downscaled to config.FIREWORKS_FRAME_MAX_WIDTH (default
    768px wide, aspect-preserved, never upscaled) before saving — a real
    test against actual 1440p/4K source clips hit "write operation timed
    out" uploading un-resized native-resolution frames; multiple multi-MB
    JPEGs add up fast on ordinary home upload bandwidth. Downscaling first
    fixes that at the source instead of just raising timeouts."""
    duration = _probe_duration_seconds(video_path)
    if max_frames <= 1:
        timestamps = [duration / 2.0]
    else:
        # Avoid sampling frame 0 (often a black/blank first frame) and the
        # very last instant (can fail to decode on some containers).
        margin = duration * 0.03
        span_start, span_end = margin, max(duration - margin, margin + 0.1)
        step = (span_end - span_start) / (max_frames - 1) if max_frames > 1 else 0
        timestamps = [span_start + step * i for i in range(max_frames)]

    max_w = config.FIREWORKS_FRAME_MAX_WIDTH
    # scale filter: shrink to max_w wide if the source is wider, otherwise
    # leave as-is (never upscale a smaller source); height auto (-2 keeps it
    # divisible by 2, which some encoders require).
    scale_filter = f"scale='min({max_w},iw)':-2"

    frames = []
    for i, ts in enumerate(timestamps):
        out_path = os.path.join(workdir, f"frame_{i:03d}.jpg")
        result = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", video_path,
             "-frames:v", "1", "-vf", scale_filter, "-q:v", "4", out_path],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0 and os.path.exists(out_path):
            with open(out_path, "rb") as f:
                frames.append((ts, f.read()))

    if not frames:
        raise RuntimeError("ffmpeg failed to extract any frames from this clip")
    return frames


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse JSON from Fireworks response: {text[:300]}")


class FireworksCaptioner:
    def __init__(self, api_key: str = None, base_url: str = None,
                 vision_model: str = None, text_model: str = None):
        self.api_key = api_key or config.FIREWORKS_API_KEY
        if not self.api_key:
            raise ValueError("Missing FIREWORKS_API_KEY (required for CAPTION_PROVIDER=fireworks_vision)")
        self.base_url = base_url or config.FIREWORKS_BASE_URL
        self.vision_model = vision_model or config.FIREWORKS_VISION_MODEL
        self.text_model = text_model or config.FIREWORKS_TEXT_MODEL

    def _chat_with_retry(self, messages: list, model: str, max_tokens: int = 1500,
                          response_format: dict = None, timeout_seconds: float = None):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.5,
        }
        if response_format:
            payload["response_format"] = response_format
        timeout = timeout_seconds if timeout_seconds is not None else config.PER_REQUEST_TIMEOUT_SECONDS

        last_exc = None
        for attempt in range(MAX_API_RETRIES + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers, json=payload,
                    timeout=timeout,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                last_exc = e
                if attempt < MAX_API_RETRIES and _is_retryable(e):
                    delay = RETRY_BACKOFF_SECONDS[attempt]
                    print(f"[retry] transient Fireworks vision error (attempt {attempt + 1}/{MAX_API_RETRIES + 1}, "
                          f"waiting {delay}s): {e}")
                    time.sleep(delay)
                    continue
                raise
        raise last_exc

    def caption_clip(self, video_path: str, styles: list, max_wait_seconds: int = 90):
        """Frames-only equivalent of GeminiCaptioner.caption_clip. Same
        return contract: (captions: dict, scene_report: str)."""
        with tempfile.TemporaryDirectory() as workdir:
            frames = _extract_frames(video_path, config.MAX_FRAMES_PER_CLIP, workdir)
            duration = _probe_duration_seconds(video_path)

            timestamps = [ts for ts, _ in frames]
            prompt_text = build_frame_scene_analysis_prompt(timestamps, duration)

            content = [{"type": "text", "text": prompt_text}]
            for ts, jpeg_bytes in frames:
                b64 = base64.b64encode(jpeg_bytes).decode("ascii")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })

            # Dedicated (longer) timeout: multiple images + a large vision
            # model legitimately need more than the shared 28s used for
            # small text-only Gemma calls elsewhere — see config.py comment.
            scene_report = self._chat_with_retry(
                messages=[{"role": "user", "content": content}],
                model=self.vision_model,
                max_tokens=1200,
                timeout_seconds=config.FIREWORKS_VISION_TIMEOUT_SECONDS,
            )

        if scene_report.upper().startswith("ANALYSIS FAILED"):
            raise SceneAnalysisFailed(scene_report)

        # --- Stage 2: caption generation, text-only, from the report ---
        # Same prompt builder as the Gemini path — it's already model-agnostic.
        prompt2 = build_caption_generation_prompt(scene_report, styles)
        raw = self._chat_with_retry(
            messages=[{"role": "user", "content": prompt2}],
            model=self.text_model,
            max_tokens=600,
            response_format={"type": "json_object"},
        )

        captions = _extract_json(raw)
        result = {s: str(captions.get(s, "")).strip() for s in styles}
        return result, scene_report
