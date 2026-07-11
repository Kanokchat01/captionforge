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
(fireworks_vision_client.FireworksCaptioner, judge_polish.JudgeAssistant, downloader.py,
config.py) so results shown here should match what the real container would
produce for the same clip.

Run locally:
    pip install -r web_demo/requirements.txt
    python web_demo/app.py
Then open http://localhost:5000 in a browser.

Needs the same .env as the main pipeline (FIREWORKS_API_KEY required).
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
from fireworks_vision_client import FireworksCaptioner, SceneAnalysisFailed as FireworksSceneAnalysisFailed
from judge_polish import JudgeAssistant
from prompts import in_word_range, word_count

app = Flask(__name__)

ALL_STYLES = ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]
HUMOR_STYLES_FOR_POLISH = {"sarcastic", "humorous_tech", "humorous_non_tech"}

_captioner = None
_judge = None


def get_clients():
    """Lazy singleton init so missing API keys surface as a clean
    JSON error on first request instead of crashing the server at import
    time (the server itself should stay up even if keys aren't set yet)."""
    global _captioner, _judge
    if _captioner is None:
        _captioner = FireworksCaptioner()
    if _judge is None:
        _judge = JudgeAssistant()
    return _captioner, _judge


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
        captioner, judge = get_clients()
    except ValueError as e:
        return jsonify({"error": f"Server is missing an API key: {e}"}), 500

    local_path = None
    t0 = time.monotonic()
    try:
        local_path = download_video(video_url)

        try:
            candidates, scene = captioner.caption_clip(local_path, styles)
        except FireworksSceneAnalysisFailed as e:
            return jsonify({"error": f"Captioner could not analyze this clip: {e}"}), 422

        def polish_with_word_guard(style, scene_hint, prompt_caption, baseline):
            # Same guard as main.py: revert a polish that pushes an in-range
            # caption out of its style's word-count range.
            polished = judge.polish(style, scene_hint, prompt_caption)
            if polished != baseline and in_word_range(style, baseline) and not in_word_range(style, polished):
                print(f"[word-guard] {style}: polish went out of range "
                      f"({word_count(baseline)} -> {word_count(polished)} words) — keeping previous caption")
                return baseline
            return polished

        final_captions = {}
        judge_used_any = False
        for style in styles:
            style_options = [c.get(style, "") for c in candidates if c.get(style)]
            # Prefer word-count-compliant candidates (same as main.py).
            compliant = [o for o in style_options if in_word_range(style, o)]
            pick_pool = compliant or style_options
            if judge.available:
                caption = judge.pick_best(style, scene, pick_pool)
                judge_used_any = judge_used_any or len(pick_pool) > 1
            else:
                caption = next(iter(pick_pool), "")
            result = caption

            if config.ENABLE_JUDGE_POLISH and judge.available and style in HUMOR_STYLES_FOR_POLISH:
                result = polish_with_word_guard(style, scene, result, result)
                judge_used_any = True

            if config.ENABLE_SELF_CRITIQUE and judge.available:
                for _ in range(config.MAX_CRITIQUE_RETRIES):
                    score, feedback = judge.judge(style, scene, result)
                    judge_used_any = True
                    if score >= config.CRITIQUE_PASS_THRESHOLD:
                        break
                    hint = f"{result} (reviewer feedback to address: {feedback})" if feedback else result
                    result = polish_with_word_guard(style, scene, hint, result)

            final_captions[style] = result or caption

        elapsed = time.monotonic() - t0
        return jsonify({
            "captions": final_captions,
            "scene_report": scene,
            "judge_available": judge.available,
            "judge_used": judge_used_any,
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
