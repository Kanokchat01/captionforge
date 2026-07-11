# CaptionForge

Track 2 (Video Captioning Agent) submission for AMD Developer Hackathon: Act II.

Watches a video clip and writes one caption per requested style —
`formal`, `sarcastic`, `humorous_tech`, `humorous_non_tech` — using a
three-model Fireworks pipeline where each model does the job it won in a
head-to-head benchmark (2026-07-11, official sample clips, cross-judged on
the official rubric by two neutral models):

| Role | Model | Why |
|---|---|---|
| Stage 1: scene analysis (vision) | `kimi-k2p6` | most detailed, meme-aware scene reports; verified hallucination-free against real frames |
| Stage 2: caption writing | `glm-5p2` | best caption writer (0.874 vs 0.850 qwen3p7-plus, 0.830 kimi-k2p7-code, 0.666 minimax-m3) |
| Best-of-N pick / judge / polish | `qwen3p7-plus` | runner-up quality, fastest, different family from the writer (no self-preference bias) |
| Stage 1 fallback (degrade chain) | `qwen3p7-plus` | vision-capable second opinion if kimi fails on a clip |

`minimax-m3` (previous default) was dropped after it failed to emit valid
JSON on 2 of 3 benchmark clips even with `response_format=json_object`.

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
must finish within **10 minutes** total (hidden eval set is ~12 clips,
30s–2min each). Scoring is caption **accuracy** (0–1) + **style match**
(0–1) per caption by an LLM judge — there is no token-count penalty in
Track 2, which is why the pipeline spends extra calls on quality
(Best-of-N + self-critique).

## Pipeline

1. **Download** with retry, `.tmp`-then-rename, and a hard wall-clock cap
   per download (`MAX_DOWNLOAD_WALL_SECONDS`, default 150s) so a slow
   trickling server can't eat the global budget.
2. **Stage 1 — Scene Report** (`kimi-k2p6`): adaptive frame sampling — one
   frame per ~8s, clamped to 8–16 frames, downscaled to 768px — into a
   structured 10-section report (subject, environment, timeline, camera,
   lighting, audio, mood, standout details, humor potential, RISKS).
   Degrade chain on failure: fewer frames → `qwen3p7-plus`.
3. **Stage 2 — Best-of-N captions** (`glm-5p2`): N=3 candidate caption sets
   generated in parallel at temperatures 0.6/0.85/1.0, text-only from the
   report.
4. **Judge pass** (`qwen3p7-plus`): picks the best candidate per style, then
   self-critique — any caption scoring below `CRITIQUE_PASS_THRESHOLD` (8/10)
   is rewritten with the judge's feedback, up to `MAX_CRITIQUE_RETRIES` (2)
   rounds. All judge/polish prompts carry the full per-style structural
   rules (word counts, banned words, emoji rules).
5. **Time budget**: clips are probed (HEAD) and scheduled heaviest-first,
   processed with `CONCURRENCY=6`; a hard wall-clock deadline
   (`TOTAL_BUDGET_SECONDS=540`) is enforced with
   `concurrent.futures.wait(..., timeout=...)` — any clip not done in time
   gets a fallback caption instead of blocking the rest. `os._exit(0)` at
   the end guarantees the process can't hang on a stuck thread.

No audio understanding on this path (Fireworks' Whisper endpoints were
discontinued 2026-06-10); prompts explicitly force "No audio present" so the
models never invent sound.

## Credentials: Track 2 injects NONE — must be baked into the image

The official guide states Track 2 injects **no** API key or model
restriction at evaluation time: *"use your own credentials inside the
container."* The judge just runs `docker run <image>` with no `-e` flags,
so `FIREWORKS_API_KEY` must be baked in at **build time** via
`--build-arg`.

Never put the real key literally in the `Dockerfile` or commit it to git —
only pass it on the build command line. The pushed public image will have
the key embedded in its layers (extractable by anyone who pulls it): treat
this hackathon key as disposable, watch the credit balance during the
event, and rotate/revoke it after the event ends.

## Setup (local dev)

```bash
cp .env.example .env   # fill in FIREWORKS_API_KEY
pip install -r requirements.txt
python src/main.py      # reads input/tasks.json, writes output/results.json
```

Set `KEEP_DOWNLOADS=true` locally to cache clips in `scratch_videos/`
between runs. Note: a full 12-clip UHD run on home bandwidth will hit the
download caps by design — the judging VM has datacenter bandwidth.

## Docker — build, test, and push

Submission requires an actual image pushed to a public registry. Judging VM
is `linux/amd64`.

```bash
# Local build/test
docker build -t captionforge .
docker run --rm \
  -e FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  -v $(pwd)/input:/input \
  -v $(pwd)/output:/output \
  captionforge

# REAL SUBMISSION BUILD — bake the credential in via --build-arg so the
# image is self-contained (the judge passes no -e flags):
docker buildx build --platform linux/amd64 \
  --build-arg FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  -t ghcr.io/<you>/captionforge:latest --push .

# Sanity-check with ZERO -e flags, exactly like the judge will run it:
docker run --rm \
  -v $(pwd)/input:/input \
  -v $(pwd)/output:/output \
  ghcr.io/<you>/captionforge:latest
```

Submissions are rate-limited to 10/hour — only submit after a clean local
Docker run.

## File map

- `src/main.py` — orchestration, concurrency, time budget, fallback handling
- `src/fireworks_vision_client.py` — Stage 1 vision + Stage 2 Best-of-N generation
- `src/judge_polish.py` — judge: pick-best, critique, polish (model set by `FIREWORKS_JUDGE_MODEL`)
- `src/prompts.py` — all prompt text, style rules, judge rubrics
- `src/downloader.py` — clip download with retry/timeout/wall-cap + size probing
- `src/config.py` — all tunables, env-var driven, benchmark notes
- `web_demo/` — local Flask demo (not part of the submission)
