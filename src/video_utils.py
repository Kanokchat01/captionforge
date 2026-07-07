"""
DEPRECATED — no longer used.

Gemini 2.5 Flash accepts the raw uploaded video file directly and natively
understands both the visual track and the embedded audio track, so we no
longer extract frames/audio with FFmpeg locally. Removing this step also
cuts image size, startup time, and per-clip latency, which matters given the
hard 10-minute total runtime limit. Kept only so old imports don't hard-crash.
"""
