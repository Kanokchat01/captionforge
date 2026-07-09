"""
Local web demo for CaptionForge.

This is NOT part of the Track 2 submission itself -- the real submission
runs headless inside Docker (see ../src/main.py, reads /input/tasks.json,
writes /output/results.json, no UI at all). This Flask app exists purely as
a convenience for trying the pipeline interactively during development and
for recording the hackathon demo video: paste a video URL, pick styles,
click a button, and see the 4 generated captions rendered nicely instead of
hand-editing input/tasks.json and rereading output/results.json every time.

It reuses the exact same pipeline code the submission uses
(gemini_client.GeminiCaptioner, gemma_polish.GemmaAssistant, downloader.py,
config.py) so results shown here should match what the real container would
produce for the same clip.

Run locally:
    pip install -r web_demo/requirements.txt
    python web_demo/app.py
Then open http://localhost:5000 in a browser.

Needs the same .env as the main pipeline (GEMINI_API_KEY required,
FIREWORKS_API_KEY optional for Gemma polish/critique).
"""
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from flask import Flask, request, jsonify, render_template

import config
from downloader import download_video
from gemini_client import GeminiCaptioner, SceneAnalysisFailed
from gemma_polish import GemmaAssistant

app = Flask(__name__)

ALL_STYLES = ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]
HUMOR_STYLES_FOR_POLISH = {"sarcastic", "humorous_tech", "humorous_non_tech"}

_gemini = None
_gemma = None


def get_clients():
    """Lazy singleton init so a missing GEMINI_API_KEY surfaces as a clean
    JSON error on first request instead of crashing the server at import
    time (the server itself should stay up even if keys aren't set yet)."""
    global _gemini, _gemma
    if _gemini is None:
        _gemini = GeminiCaptioner()
    if _gemma is None:
        _gemma = GemmaAssistant()
    return _gemini, _gemma


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    video_url = (data.get("video_url") or "").strip()
    requested_styles = data.get("styles") or ALL_STYLES
    styles = [s for s in requested_styles if s in ALL_STYLES] or ALL_STYLES

    if not video_url:
        return jsonify({"error": "Please provide a video URL."}), 400

    try:
        gemini, gemma = get_clients()
    except ValueError as e:
        return jsonify({"error": f"Server is missing an API key: {e}"}), 500

    local_path = None
    t0 = time.monotonic()
    try:
        local_path = download_video(video_url)

        try:
            base_captions, scene = gemini.caption_clip(local_path, styles)
        except SceneAnalysisFailed as e:
            return jsonify({"error": f"Gemini could not analyze this clip: {e}"}), 422

        final_captions = {}
        gemma_used_any = False
        for style, caption in base_captions.items():
            result = caption

            if config.ENABLE_GEMMA_POLISH and gemma.available and style in HUMOR_STYLES_FOR_POLISH:
                result = gemma.polish(style, scene, result)
                gemma_used_any = True

            if config.ENABLE_SELF_CRITIQUE and gemma.available:
                for _ in range(config.MAX_CRITIQUE_RETRIES):
                    score, feedback = gemma.judge(style, scene, result)
                    gemma_used_any = True
                    if score >= config.CRITIQUE_PASS_THRESHOLD:
                        break
                    hint = f"{result} (reviewer feedback to address: {feedback})" if feedback else result
                    result = gemma.polish(style, scene, hint)

            final_captions[style] = result or caption

        elapsed = time.monotonic() - t0
        return jsonify({
            "captions": final_captions,
            "scene_report": scene,
            "gemma_available": gemma.available,
            "gemma_used": gemma_used_any,
            "elapsed_seconds": round(elapsed, 1),
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass


if __name__ == "__main__":
    print("[*] CaptionForge demo running at http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
