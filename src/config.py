"""
Central config. All values overridable via environment variables so the
Track 2 rules ("no restriction, use your own credentials") are respected —
nothing is hardcoded, nothing bundled into the image.
"""
import os

# --- Required for the primary (base caption) pass ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# --- Which engine analyzes the raw video and writes the Scene Report ---
# "fireworks_vision" (default as of the real 12-clip test): extracts frames
# with ffmpeg and sends them as images to a Fireworks-hosted vision model
# (MiniMax M3), then writes captions via a Fireworks text call — same 2-stage
# shape as the Gemini path. Chosen as the main path because it: (a) verified
# working end-to-end on a real 12-clip run (124.2s, 0 timeouts, good caption
# quality) at the actual hidden-eval scale, (b) doesn't depend on Gemini's
# finicky free-tier request quota at all, (c) consolidates everything onto
# Fireworks credentials already in use for the Gemma bonus. Trade-off: this
# path is frames-only — NO audio understanding. Fireworks' own chat
# completions endpoint has no confirmed raw-video-file input (only image_url
# in their own docs/examples), and Fireworks' Whisper/audio-transcription
# endpoints were confirmed discontinued (returning 401) as of 2026-06-10, so
# there is currently no way to recover audio understanding on this path.
# "gemini": fallback/alternate — Gemini reads the video file natively
# (video+audio), proven at 8-clip scale, but subject to Gemini's own
# per-project free-tier request quota (see gemini_client.py comments).
CAPTION_PROVIDER = os.environ.get("CAPTION_PROVIDER", "fireworks_vision").lower()  # "fireworks_vision" | "gemini"
FIREWORKS_VISION_MODEL = os.environ.get("FIREWORKS_VISION_MODEL", "accounts/fireworks/models/minimax-m3")
FIREWORKS_TEXT_MODEL = os.environ.get("FIREWORKS_TEXT_MODEL", "accounts/fireworks/models/minimax-m3")
MAX_FRAMES_PER_CLIP = int(os.environ.get("MAX_FRAMES_PER_CLIP", "8"))
# Real test with actual 1440p/4K source clips hit "write operation timed
# out" uploading un-resized frames (a handful of multi-MB JPEGs at native
# resolution add up fast on typical home upload bandwidth). Downscale before
# base64-encoding — 768px is plenty for scene description and cuts payload
# size drastically, which also lowers Fireworks vision-token cost.
FIREWORKS_FRAME_MAX_WIDTH = int(os.environ.get("FIREWORKS_FRAME_MAX_WIDTH", "768"))
# The vision call (multiple images + a 428B-param model) legitimately needs
# more headroom than the shared PER_REQUEST_TIMEOUT_SECONDS (28s, tuned for
# small text-only Gemma calls) — same real test above also timed out on the
# upload itself before the frame-size fix, so this is a second, independent
# safety margin on top of that fix, not a substitute for it.
FIREWORKS_VISION_TIMEOUT_SECONDS = float(os.environ.get("FIREWORKS_VISION_TIMEOUT_SECONDS", "60"))

# --- Optional secondary pass: Gemma polish + self-critique via Fireworks,
#     purely to qualify for the Best Use of Gemma bonus prize. Must never
#     block or crash the primary submission if unavailable. ---
FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
FIREWORKS_GEMMA_MODEL = os.environ.get("FIREWORKS_GEMMA_MODEL", "accounts/fireworks/models/gemma-3-27b-it")

# --- DEV/TEST-ONLY alternate Gemma provider (OpenRouter's free tier) ---
# The official hackathon rule for the Best Use of Gemma bonus ($3,000 for
# Track 2) states Gemma must be accessed "through Fireworks AI and AMD
# Developer Cloud" for this hackathon. OpenRouter's free Gemma model is
# useful for cheap local iteration (doesn't burn the limited $50 Fireworks
# credit while tuning prompts), but the REAL SUBMISSION BUILD must use
# Fireworks (the default) to remain eligible for that bonus. Never set
# GEMMA_PROVIDER=openrouter in the Dockerfile/--build-arg for the actual
# submission image — leave it unset (defaults to "fireworks") there.
GEMMA_PROVIDER = os.environ.get("GEMMA_PROVIDER", "fireworks").lower()  # "fireworks" | "openrouter"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_GEMMA_MODEL = os.environ.get("OPENROUTER_GEMMA_MODEL", "google/gemma-3-27b-it:free")

ENABLE_GEMMA_POLISH = os.environ.get("ENABLE_GEMMA_POLISH", "true").lower() == "true"
ENABLE_SELF_CRITIQUE = os.environ.get("ENABLE_SELF_CRITIQUE", "true").lower() == "true"
MAX_CRITIQUE_RETRIES = int(os.environ.get("MAX_CRITIQUE_RETRIES", "2"))
CRITIQUE_PASS_THRESHOLD = float(os.environ.get("CRITIQUE_PASS_THRESHOLD", "8"))

# --- Orchestration / time-budget (hard rule: whole container <= 10 minutes) ---
INPUT_PATH = os.environ.get("TASKS_INPUT_PATH", "/input/tasks.json" if os.path.exists("/input/tasks.json") else "input/tasks.json")
OUTPUT_PATH = os.environ.get("RESULTS_OUTPUT_PATH", "/output/results.json" if os.path.exists("/output") else "output/results.json")
CONCURRENCY = int(os.environ.get("CONCURRENCY", "4"))
# Hard limit is 600s (10 min). Leave a safety margin for the final JSON write.
TOTAL_BUDGET_SECONDS = float(os.environ.get("TOTAL_BUDGET_SECONDS", "540"))
# Rule: response time per request must be under 30s.
PER_REQUEST_TIMEOUT_SECONDS = float(os.environ.get("PER_REQUEST_TIMEOUT_SECONDS", "28"))

# Reserved purely for writing the final results.json + process exit. If a
# worker is still running when (deadline - this) is reached, its result is
# NOT waited for any further — main.py fills a fallback immediately instead.
FINALIZATION_RESERVE_SECONDS = float(os.environ.get("FINALIZATION_RESERVE_SECONDS", "30"))

# If a task is picked up by a worker with less than this much time left on
# the global clock, don't even start the (expensive) captioning call — go
# straight to a fallback caption. Prevents starting doomed work.
CRITICAL_TIME_THRESHOLD_SECONDS = float(os.environ.get("CRITICAL_TIME_THRESHOLD_SECONDS", "45"))

REQUIRED_STYLES = {"formal", "sarcastic", "humorous_tech", "humorous_non_tech"}
