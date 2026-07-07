"""
Primary caption generator: Gemini 2.5 Flash, native video+audio multimodal
input, single call per clip returns all requested styles as JSON.
No separate FFmpeg/Whisper pass needed — Gemini understands the audio track
that's embedded in the uploaded video file directly.
"""
import json
import re
import time

from google import genai
from google.genai import types

import config
from prompts import build_caption_prompt


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


class GeminiCaptioner:
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("Missing GEMINI_API_KEY")
        self.model = model or config.GEMINI_MODEL
        self.client = genai.Client(api_key=self.api_key)

    def caption_clip(self, video_path: str, styles: list, max_wait_seconds: int = 90) -> dict:
        """Upload the clip, wait for it to become ACTIVE, then request all
        requested styles in one JSON-mode generation call."""
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

        prompt = build_caption_prompt(styles)
        response = self.client.models.generate_content(
            model=self.model,
            contents=[video_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )

        try:
            self.client.files.delete(name=video_file.name)
        except Exception:
            pass

        captions = _extract_json(response.text)
        # Keep only the styles that were actually requested, as strings.
        return {s: str(captions.get(s, "")).strip() for s in styles}

    def scene_hint(self, styles_result: dict) -> str:
        """Cheap scene summary reused as grounding context for the Gemma
        polish/judge passes, built from the formal caption if present."""
        return styles_result.get("formal") or next(iter(styles_result.values()), "")
