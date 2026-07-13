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
# v8: shipped engine is minimax_single — ONE JSON call per clip for all four
# styles. qwen_direct's 4-calls-per-clip put 16 requests in flight at once and
# 48-90 on the wire per run; the board scored that 0.66 and 0.69 (~4-5 of 12
# clips lost to 429s and shipped as generic fallbacks). Both teams currently
# scoring 0.91 use one call per clip. This is a call-volume fix, not a prompt
# change: the personas are r1's, verbatim.
ARG CAPTION_ASSEMBLY="minimax_single"
# Which model answers the single JSON call. SwiftCap (0.91) runs minimax-m3.
ARG MINIMAX_SINGLE_MODEL=""
ENV MINIMAX_SINGLE_MODEL=${MINIMAX_SINGLE_MODEL}
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

# With minimax_single there is exactly ONE call per clip, so CONCURRENCY *is*
# the number of requests in flight: 2, against the 16 that qwen_direct put up.
# SwiftCap runs its 12 clips strictly sequentially (1 in flight) and scores
# 0.91, so 2 is already the aggressive end of proven territory. 12 clips at
# ~20-30s each, 2 at a time, lands around 150-200s of the 540s budget.
ENV CONCURRENCY="2"

# NOTE: there is deliberately no QWEN_DIRECT_MAX_INFLIGHT here. r6 added a
# global semaphore capping TOTAL in-flight vision calls at 3 while the
# pipeline wants 16, which serialized the run on the (slower) judge box until
# clips hit the time cutoff and shipped generic fallbacks. Throttling the
# START of clips is safe (HARDEN_START_STAGGER); capping steady-state
# throughput is not. Do not reintroduce it.

# No CLI args: the harness runs the container, main.py reads /input/tasks.json
# and writes /output/results.json on its own, then exits 0.
CMD ["python", "main.py"]
