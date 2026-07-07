# CaptionForge

Track 2 (Video Captioning Agent) submission for AMD Developer Hackathon: Act II.

Watches a video clip and writes one caption per requested style —
`formal`, `sarcastic`, `humorous_tech`, `humorous_non_tech` — using Gemini 2.5
Flash for native video+audio understanding, with an optional Gemma
(Fireworks AI) polish + self-critique pass targeting the Best Use of Gemma
bonus prize.

## Official I/O contract (do not change)

Reads `/input/tasks.json`:
```json
[{"task_id": "v1", "video_url": "https://...", "styles": ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]}]
```

Writes `/output/results.json`:
```json
[{"task_id": "v1", "captions": {"formal": "...", "sarcastic": "...", "humorous_tech": "...", "humorous_non_tech": "..."}}]
```

Style keys use underscores, not hyphens — must match exactly what each
task's `styles` list requests, or that clip scores zero for the missing
style. Container must exit 0, must be ready within 60s, and the whole run
must finish within **10 minutes** total (hidden eval set is ~12 clips).

## Setup (local dev)

```bash
cp .env.example .env   # fill in GEMINI_API_KEY (required), FIREWORKS_API_KEY (optional)
pip install -r requirements.txt
python src/main.py      # reads input/tasks.json, writes output/results.json
```

## Docker — build, test, and push

Submission requires an actual image pushed to a public registry, not just a
Dockerfile in the repo. Judging VM is `linux/amd64`.

```bash
# On Apple Silicon, add --platform linux/amd64
docker build -t captionforge .

# Local test run (mount /input and /output, pass env vars)
docker run --rm \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  -v $(pwd)/input:/input \
  -v $(pwd)/output:/output \
  captionforge

# Push (adjust to your registry)
docker buildx build --platform linux/amd64 -t ghcr.io/<you>/captionforge:latest --push .
```

## Design notes / risks to keep testing against

- **No FFmpeg/Whisper step.** Gemini 2.5 Flash reads the video file directly
  and understands the embedded audio natively, so there's no separate
  audio-extraction pass to keep in budget.
- **10-minute hard ceiling drives the architecture.** Clips are processed
  concurrently (`CONCURRENCY` in `.env`, default 4) instead of one at a time.
  `TOTAL_BUDGET_SECONDS` (default 540s, 1-minute safety margin) is checked
  before starting the optional Gemma polish/self-critique steps for each
  caption — if the budget's tight, the pipeline ships the raw Gemini caption
  instead of skipping the clip entirely.
- **Self-critique is capped**, `MAX_CRITIQUE_RETRIES=2`, to avoid infinite
  loops and to bound worst-case latency per clip.
- **Gemma polish/critique failures never break a clip** — every Fireworks
  call in `gemma_polish.py` falls back to the unpolished Gemini caption on
  any exception.
- **Must generalize beyond the 3 sample clips** in `input/tasks.json` — the
  hidden eval set spans nature, urban, animals, people, sports, food,
  weather, and technology. Don't tune prompts to only these three scenes.
- **Untested assumption:** actual upload+processing latency for large 4K
  sample clips on Gemini's side. Time a real run against all 3 sample clips
  first and tune `TOTAL_BUDGET_SECONDS` / `CONCURRENCY` / the
  `max_wait_seconds` in `gemini_client.py` before relying on the defaults.

## File map

- `src/main.py` — orchestration, concurrency, time budget, fallback handling
- `src/gemini_client.py` — primary caption generation (Gemini 2.5 Flash)
- `src/gemma_polish.py` — optional Gemma polish + self-critique (Fireworks)
- `src/prompts.py` — all prompt text and style definitions
- `src/downloader.py` — clip download with retry/timeout
- `src/config.py` — all tunables, env-var driven
- `judge.py`, `fireworks_client.py`, `video_utils.py` — deprecated, kept only
  so old imports don't crash; do not extend these
