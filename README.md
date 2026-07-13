# CaptionForge

**Track 2 — Video Captioning Agent · AMD Developer Hackathon: Act II**

An AI agent that watches a video clip and writes it up in four distinct
voices — `formal`, `sarcastic`, `humorous_tech`, and `humorous_non_tech` —
every one of them grounded in the same frames, so no style drifts away from
what is actually on screen. Built on Fireworks-hosted vision models with
deterministic, in-code guards for style and reliability.

---

## How it works

One clip → one multimodal call → four finished captions.

```
tasks.json ─▶ sample frames ─▶ ONE vision call ─▶ {4 styles as JSON} ─▶ guards ─▶ results.json
              (adaptive 8–24        (qwen3p7-plus,       (regex style checks,
               @640px)               all styles at once)   rescue ladder)
```

Rather than chaining a describer, a writer, and an LLM judge — or firing one
call per style — CaptionForge asks a single vision model for **all four
captions at once, as one JSON object**. Every style is written from the same
evidence in the same breath, so the four can never disagree about what the
video shows, and a 12-clip run costs ~12 API calls instead of ~50. In a
timed, rate-limited environment, call volume *is* the reliability budget.

### Design principles

| Principle | What it means in the code |
|---|---|
| **One call per clip** | `minimax_single` engine returns all four styles in a single JSON reply. Fewer calls, fewer failure points, no cross-style contradictions. |
| **Code enforces style, not a second AI** | No emoji, no banned slang, a required tech term in `humorous_tech`, zero jargon in `humorous_non_tech` — all checked by deterministic regex after generation. A cross-style overlap guard rejects near-duplicate captions. |
| **Reliability is engineered, not assumed** | A missing style zeroes the whole clip, so the pipeline never lets one happen. Under every failure it climbs a rescue ladder before it ever ships a generic caption (see below). |
| **Grounded by design** | Prompts ban quoting on-screen text and naming real cities or landmarks — the two most common ways a vision model invents detail it cannot verify. |

### The rescue ladder

Each clip has four rungs below the main call. A generic fallback keeps style
credit but scores ~0 on accuracy, so it is always the last resort:

1. **Stricter retry** — one re-ask carrying the exact validation problems back to the model.
2. **Per-style rescue** — any still-missing style is re-generated on a different call geometry.
3. **URL-frame fallback** — if the download dies, pull frames straight off the video URL by HTTP range request instead of losing the clip.
4. **Generic caption** — style-correct, content-free, guaranteed non-empty. Last resort only.

Retries are **jittered and clock-aware** (never sleep into a retry the budget
can't fit), clip starts are **staggered** to avoid a rate-limit thundering
herd, and a hard wall-clock guard keeps every run under the 10-minute limit.
The container always exits 0 with a valid `results.json`.

---

## Official I/O contract *(do not change)*

**Reads** `/input/tasks.json`:
```json
[{"task_id": "v1", "video_url": "https://...", "styles": ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]}]
```

**Writes** `/output/results.json`:
```json
[{"task_id": "v1", "captions": {"formal": "...", "sarcastic": "...", "humorous_tech": "...", "humorous_non_tech": "..."}}]
```

Style keys use **underscores, not hyphens**, and must match each task's
`styles` list exactly. The container must exit 0, be ready within 60s, and
finish the whole run within **10 minutes**. Every requested style is
guaranteed a caption on every path (fallbacks, never crashes), with a hard
global time budget and heaviest-clip-first scheduling.

---

## Credentials — Track 2 injects none

The official guide states Track 2 supplies **no** API key or model
restriction at judging time: *"use your own credentials inside the
container."* The judge runs `docker run <image>` with **no `-e` flags**, so
`FIREWORKS_API_KEY` is baked in at **build time** via `--build-arg` — passed
only on the build command line, never written into the `Dockerfile` or
committed to git. Other `.env` keys (local dev/eval only) stay local and are
never baked. The hackathon key is treated as disposable and rotated after
the event.

---

## Quick start

**Local dev**
```bash
cp .env.example .env          # fill in FIREWORKS_API_KEY
pip install -r requirements.txt
python src/main.py            # reads input/tasks.json → writes output/results.json
```
On home bandwidth, set `KEEP_DOWNLOADS=true` (caches clips in
`scratch_videos/`), `CONCURRENCY=1`, and raise `TOTAL_BUDGET_SECONDS` — the
defaults are tuned for the judging VM's datacenter bandwidth.

**Build & submit** *(judging VM is `linux/amd64`)*
```bash
# Real submission build — self-contained, key baked in, pushed to a public registry:
docker buildx build --platform linux/amd64 \
  --build-arg FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  -t ghcr.io/<you>/captionforge:latest --push .

# Sanity-check exactly like the judge runs it — ZERO -e flags:
docker run --rm -v $(pwd)/input:/input -v $(pwd)/output:/output \
  ghcr.io/<you>/captionforge:latest
```
Submissions are rate-limited to 10/hour — only submit after a clean local
run. `.dockerignore` trims the build context to `requirements.txt` + `src/`;
docs, the web demo, `.venv`, and `.env` never reach the image.

**Web demo** *(optional, not part of the submission)*
```bash
pip install -r web_demo/requirements.txt
python web_demo/app.py         # http://localhost:5000
```

---

## Project layout

| Path | Role |
|---|---|
| `src/main.py` | Orchestration: concurrency, time budget, startup guards, fallbacks |
| `src/minimax_single.py` | **Primary engine** — one JSON call per clip, all four styles |
| `src/qwen_direct.py` | Per-style rescue engine (different call geometry) |
| `src/fireworks_vision_client.py` | Fireworks client + ffmpeg frame extraction |
| `src/prompts.py` | Prompt construction + deterministic style checks |
| `src/downloader.py` | Clip download with retry / timeout / wall-cap + size probe |
| `src/config.py` | All tunables, env-var driven |
| `scripts/` | Local dev & eval tooling (never in the image) |
| `web_demo/` | Flask demo UI (not part of the submission) |
| `Dockerfile` | Track 2 submission image (headless, key baked at build) |
| `Dockerfile.web` | Hosted demo image (web server, key supplied at run time) |
| `docs/` | Official Participant Guide |
