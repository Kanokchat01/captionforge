"""
Secondary pass: Gemma (via Fireworks AI, team's own credentials — Track 2
injects no restriction) used to (a) polish sarcastic/humorous_tech captions
and (b) self-critique every caption before submission. This whole module is
optional-by-design: if Fireworks is unavailable or errors, callers must fall
back to the Gemini-only caption rather than fail the clip.
"""
import json
import re

import requests

import config
from prompts import (
    GEMMA_POLISH_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    build_gemma_polish_prompt,
    build_judge_prompt,
)


class GemmaAssistant:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or config.FIREWORKS_API_KEY
        self.base_url = base_url or config.FIREWORKS_BASE_URL
        self.model = model or config.FIREWORKS_GEMMA_MODEL

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 250,
                "temperature": 0.7,
            },
            timeout=config.PER_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def polish(self, style: str, scene_hint: str, draft_caption: str) -> str:
        if not self.available:
            return draft_caption
        try:
            return self._chat(
                GEMMA_POLISH_SYSTEM_PROMPT,
                build_gemma_polish_prompt(style, scene_hint, draft_caption),
            )
        except Exception:
            return draft_caption  # never let polish failures break the pipeline

    def judge(self, style: str, scene_hint: str, caption: str):
        """Returns (score: float, feedback: str). Defaults to a passing
        score if the judge call itself fails, so we don't retry forever
        on infra errors."""
        if not self.available:
            return 10.0, ""
        try:
            raw = self._chat(JUDGE_SYSTEM_PROMPT, build_judge_prompt(style, scene_hint, caption))
            data = _extract_json(raw)
            return float(data.get("score", 10)), str(data.get("feedback", ""))
        except Exception:
            return 10.0, ""


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
