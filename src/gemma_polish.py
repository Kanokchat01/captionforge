"""
Secondary pass: Gemma (via Fireworks AI, team's own credentials — Track 2
injects no restriction) used to (a) polish sarcastic/humorous_tech captions
and (b) self-critique every caption before submission. This whole module is
optional-by-design: if Fireworks is unavailable or errors, callers must fall
back to the base caption rather than fail the clip.
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
        # provider defaults to "fireworks" (config.GEMMA_PROVIDER) — the
        # sanctioned access method for the Best Use of Gemma bonus. Explicit
        # constructor args always win (used by tests / one-off overrides);
        # otherwise pick Fireworks vs OpenRouter based on config.
        # See config.py's GEMMA_PROVIDER comment: OpenRouter is DEV/TEST ONLY,
        # never for the real submission build.
        self.provider = config.GEMMA_PROVIDER
        if api_key or base_url or model:
            self.api_key = api_key or config.FIREWORKS_API_KEY
            self.base_url = base_url or config.FIREWORKS_BASE_URL
            self.model = model or config.FIREWORKS_GEMMA_MODEL
        elif self.provider == "openrouter" and config.OPENROUTER_API_KEY:
            print("[!] GemmaAssistant using OpenRouter (dev/test only) — "
                  "the real submission build must use Fireworks to stay "
                  "eligible for the Best Use of Gemma bonus.")
            self.api_key = config.OPENROUTER_API_KEY
            self.base_url = config.OPENROUTER_BASE_URL
            self.model = config.OPENROUTER_GEMMA_MODEL
        else:
            self.api_key = config.FIREWORKS_API_KEY
            self.base_url = config.FIREWORKS_BASE_URL
            self.model = config.FIREWORKS_GEMMA_MODEL

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.provider == "openrouter":
            # Optional but recommended by OpenRouter so free-tier requests
            # are attributed to this app rather than showing as anonymous.
            headers["HTTP-Referer"] = "https://github.com/Kanokchat01/captionforge"
            headers["X-Title"] = "CaptionForge"
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
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
            result = self._chat(
                GEMMA_POLISH_SYSTEM_PROMPT,
                build_gemma_polish_prompt(style, scene_hint, draft_caption),
            )
            # Diagnostic-only log so we can actually confirm real Fireworks
            # Gemma calls are succeeding (previous test runs never got far
            # enough to reach this stage, so it had never been visually
            # confirmed working end-to-end). Cheap and harmless to leave in
            # for the real submission run too — just stdout noise, no
            # behavior change either way.
            print(f"[gemma-polish] {style} via {self.provider}/{self.model}: OK "
                  f"({len(draft_caption)} -> {len(result)} chars)")
            return result
        except Exception as e:
            print(f"[gemma-polish] {style} via {self.provider}/{self.model}: FAILED ({e}) — keeping draft caption")
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
            score, feedback = float(data.get("score", 10)), str(data.get("feedback", ""))
            print(f"[gemma-judge] {style} via {self.provider}/{self.model}: OK (score={score})")
            return score, feedback
        except Exception as e:
            print(f"[gemma-judge] {style} via {self.provider}/{self.model}: FAILED ({e}) — defaulting to pass")
            return 10.0, ""


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
