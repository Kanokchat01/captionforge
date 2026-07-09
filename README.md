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

## Credentials: Track 2 injects NONE — must be baked into the image

Unlike Track 1 (which has `FIREWORKS_API_KEY`/`FIREWORKS_BASE_URL`/`ALLOWED_MODELS`
injected by the harness), the official guide states Track 2 injects **no**
API key or model restriction at evaluation time: *"use your own credentials
inside the container."* The judge just runs `docker run <image>` with no
`-e` flags. That means our own `GEMINI_API_KEY` (and optionally
`FIREWORKS_API_KEY`) must be baked into the image itself at **build time**
via `--build-arg` — relying on `-e` at `docker run` only works for our own
local testing, not for the real submission.

Never put the real key literally in the `Dockerfile` or commit it to git —
only pass it on the `docker build`/`buildx build` command line (see below).
The pushed image will have the key embedded in its layers; treat this
hackathon key as disposable and rotate/revoke it after the event ends.

## Gemma bonus: Fireworks is required, OpenRouter is dev/test only

The official hackathon page states Gemma is accessed "through Fireworks AI
and AMD Developer Cloud" for this event — that's the sanctioned path for the
**Best Use of Gemma bonus ($3,000 for Track 2)**. To avoid burning the
limited $50 Fireworks credit while iterating on prompts, `gemma_polish.py`
supports an optional dev-only override to OpenRouter's free Gemma model
(`GEMMA_PROVIDER=openrouter` in `.env`, see `.env.example`). **Never set
this for the real submission build** — leave `GEMMA_PROVIDER` unset (it
defaults to `"fireworks"`) so the pushed image only ever calls Gemma via
Fireworks. The Dockerfile does not bake `GEMMA_PROVIDER` or
`OPENROUTER_API_KEY` at all, so the submission image is safe by default
even if you forget to unset it locally.

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
# Local build/test — either -e at `docker run` OR --build-arg both work here,
# since this is just for our own testing.
docker build -t captionforge .
docker run --rm \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  -v $(pwd)/input:/input \
  -v $(pwd)/output:/output \
  captionforge

# REAL SUBMISSION BUILD — bake credentials in via --build-arg so the image
# is self-contained (the judge will not pass any -e flags). Run this exact
# form before the final push:
docker buildx build --platform linux/amd64 \
  --build-arg GEMINI_API_KEY=$GEMINI_API_KEY \
  --build-arg FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  -t ghcr.io/<you>/captionforge:latest --push .

# Sanity-check it actually works with ZERO -e flags, exactly like the judge
# will run it:
docker run --rm \
  -v $(pwd)/input:/input \
  -v $(pwd)/output:/output \
  ghcr.io/<you>/captionforge:latest
```

## Design notes / risks to keep testing against

- **No FFmpeg/Whisper step.** Gemini 2.5 Flash reads the video file directly
  and understands the embedded audio natively, so there's no separate
  audio-extraction pass to keep in budget.
- **10-minute hard ceiling drives the architecture.** Clips are probed and
  scheduled heaviest-first, processed concurrently (`CONCURRENCY` in `.env`,
  default 4), and a hard wall-clock deadline (`TOTAL_BUDGET_SECONDS`) is
  enforced with `concurrent.futures.wait(..., timeout=...)` — any clip not
  done in time gets an immediate fallback caption instead of blocking the
  rest of the run. `os._exit(0)` at the end guarantees the process can't
  hang waiting on a stuck background thread.
- **Self-critique is capped**, `MAX_CRITIQUE_RETRIES=2`, to avoid infinite
  loops and to bound worst-case latency per clip.
- **Gemma polish/critique failures never break a clip** — every Fireworks
  call in `gemma_polish.py` falls back to the unpolished Gemini caption on
  any exception.
- **2-stage prompt pipeline** (`prompts.py`): Stage 1 asks Gemini for a
  structured 10-section Scene Report (subject, environment, timeline,
  camera, lighting, audio, mood, standout details, humor potential, and a
  RISKS section listing what is NOT shown, to suppress hallucination).
  Stage 2 is a text-only call that writes the 4 styled captions from that
  report only, following strict word-count/banned-word/structural rules.
- **Must generalize beyond the 3 sample clips** in `input/tasks.json` — the
  hidden eval set spans nature, urban, animals, people, sports, food,
  weather, and technology. Don't tune prompts to only these three scenes.
- **Timing rule ambiguity:** the general rules list "response time per
  request must be under 30 seconds" for all tracks, but Track 2's own
  section only specifies the 10-minute total budget with no per-clip cap —
  a single Gemini video-analysis call can legitimately take longer than 30s
  for a 2-minute 4K clip. Read is that the 30s rule targets Track 1's
  live request/response pattern; Track 2's explicit 10-minute total is the
  governing constraint here. Flagged as an assumption, not a certainty.

## File map

- `src/main.py` — orchestration, concurrency, time budget, fallback handling
- `src/gemini_client.py` — primary caption generation (Gemini 2.5 Flash, 2-stage)
- `src/gemma_polish.py` — optional Gemma polish + self-critique (Fireworks)
- `src/prompts.py` — all prompt text and style definitions
- `src/downloader.py` — clip download with retry/timeout + size probing
- `src/config.py` — all tunables, env-var driven
- `judge.py`, `fireworks_client.py`, `video_utils.py` — deprecated, kept only
  so old imports don't crash; do not extend these
