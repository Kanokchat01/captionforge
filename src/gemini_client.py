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

    def _upload_and_wait(self, video_path: str, max_wait_seconds: int):
        video_file = self.client.files.upload(file=video_path)
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
            analysis_resp = self.client.models.generate_content(
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
        gen_resp = self.client.models.generate_content(
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
