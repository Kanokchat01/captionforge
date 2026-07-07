"""
DEPRECATED — superseded by `gemma_polish.GemmaAssistant.judge()`.

Kept only so old imports don't hard-crash. Do not add new code here.
Reason for the change: the official Participant Guide (Track 2) scores on
caption accuracy + style match via an LLM-Judge, and our self-critique loop
now needs a strict retry cap + shared time budget to fit inside the 10
minute container limit — that logic lives in main.py + gemma_polish.py.
"""
from gemma_polish import GemmaAssistant  # noqa: F401
