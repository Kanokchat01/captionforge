# Build for the judging VM's architecture (linux/amd64). If building on
# Apple Silicon: docker buildx build --platform linux/amd64 -t <tag> --push .
FROM python:3.11-slim

# ffmpeg/ffprobe are required by the frame-extraction pipeline
# (fireworks_vision_client.py).
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1
WORKDIR /app/src

# --- Track 2 credential baking ---
# The official Participant Guide states that Track 2 injects NO API key at
# evaluation time ("use your own credentials inside the container") — unlike
# Track 1, the judge just runs `docker run <image>` with no -e flags. So our
# own credentials must be baked into the image itself at build time via
# --build-arg, not supplied at `docker run` time. Never put the real key
# literally in this file or commit it — only pass it on the build command
# line (see README.md for the exact submission build command).
# ONLY the Fireworks key goes in. OPENROUTER_API_KEY is a local-eval-only
# credential and must NEVER be baked: this image is publicly pullable.
ARG FIREWORKS_API_KEY=""
ENV FIREWORKS_API_KEY=${FIREWORKS_API_KEY}

# --- v6 engine knobs (baked per submission rung; empty string = default) ---
ARG CAPTION_ASSEMBLY="qwen_direct"
# Empty = config default (qwen3p7-plus). Baked for the minimax model-swap
# rung (E1): --build-arg QWEN_DIRECT_MODEL=accounts/fireworks/models/minimax-m3
ARG QWEN_DIRECT_MODEL=""
ENV QWEN_DIRECT_MODEL=${QWEN_DIRECT_MODEL}
ARG QWEN_DIRECT_GUARD_LEVEL="1"
ARG QWEN_DIRECT_FRAMES="4"
ARG QWEN_DIRECT_TEMP_FORMAL=""
ARG QWEN_DIRECT_TEMP_SARCASTIC=""
ARG QWEN_DIRECT_TEMP_HUMOROUS_TECH=""
ARG QWEN_DIRECT_TEMP_HUMOROUS_NON_TECH=""
ENV CAPTION_ASSEMBLY=${CAPTION_ASSEMBLY} \
    QWEN_DIRECT_GUARD_LEVEL=${QWEN_DIRECT_GUARD_LEVEL} \
    QWEN_DIRECT_FRAMES=${QWEN_DIRECT_FRAMES} \
    QWEN_DIRECT_TEMP_FORMAL=${QWEN_DIRECT_TEMP_FORMAL} \
    QWEN_DIRECT_TEMP_SARCASTIC=${QWEN_DIRECT_TEMP_SARCASTIC} \
    QWEN_DIRECT_TEMP_HUMOROUS_TECH=${QWEN_DIRECT_TEMP_HUMOROUS_TECH} \
    QWEN_DIRECT_TEMP_HUMOROUS_NON_TECH=${QWEN_DIRECT_TEMP_HUMOROUS_NON_TECH}

# 6 clips x 4 styles = 24 parallel vision calls, which clusters into 429s;
# 4x4=16 keeps under it and the engine is fast enough (~10s/clip) that the
# 540s budget still clears with huge headroom. This is the value baked into
# the board-verified 0.90 image — do not change it without a board re-verify.
ENV CONCURRENCY="4"

# NOTE: there is deliberately no QWEN_DIRECT_MAX_INFLIGHT here. r6 added a
# global semaphore capping TOTAL in-flight vision calls at 3 while the
# pipeline wants 16, which serialized the run on the (slower) judge box until
# clips hit the time cutoff and shipped generic fallbacks. Throttling the
# START of clips is safe (HARDEN_START_STAGGER); capping steady-state
# throughput is not. Do not reintroduce it.

# No CLI args: the harness runs the container, main.py reads /input/tasks.json
# and writes /output/results.json on its own, then exits 0.
CMD ["python", "main.py"]
