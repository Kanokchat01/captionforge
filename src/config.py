"""
Central config. All values overridable via environment variables so the
Track 2 rules ("no restriction, use your own credentials") are respected —
nothing is hardcoded, nothing bundled into the image.
"""
import os

# --- Required for the primary (base caption) pass ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# --- Optional secondary pass: Gemma polish + self-critique via Fireworks,
#     purely to qualify for the Best Use of Gemma bonus prize. Must never
#     block or crash the primary submission if unavailable. ---
FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
FIREWORKS_GEMMA_MODEL = os.environ.get("FIREWORKS_GEMMA_MODEL", "accounts/fireworks/models/gemma3-27b-it")

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

REQUIRED_STYLES = {"formal", "sarcastic", "humorous_tech", "humorous_non_tech"}
