# Build for the judging VM's architecture (linux/amd64). If building on
# Apple Silicon: docker buildx build --platform linux/amd64 -t <tag> --push .
FROM python:3.11-slim

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
ARG GEMINI_API_KEY=""
ARG FIREWORKS_API_KEY=""
ENV GEMINI_API_KEY=${GEMINI_API_KEY}
ENV FIREWORKS_API_KEY=${FIREWORKS_API_KEY}

# No CLI args: the harness runs the container, main.py reads /input/tasks.json
# and writes /output/results.json on its own, then exits 0.
CMD ["python", "main.py"]
