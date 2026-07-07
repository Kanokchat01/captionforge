"""
CaptionForge — Track 2: Video Captioning Agent

Reads /input/tasks.json, for each task downloads the clip, generates one
caption per requested style with Gemini 2.5 Flash (native video+audio
understanding), optionally polishes + self-critiques sarcastic/humor styles
via Gemma (Fireworks, own credentials) for the Gemma bonus prize, then
writes /output/results.json. Must exit 0, must finish within 10 minutes
total, must never crash the whole run because one clip failed.
"""
import json
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

load_dotenv()  # no-op in the real submission container (no .env bundled); used for local dev

import config
from downloader import download_video
from gemini_client import GeminiCaptioner
from gemma_polish import GemmaAssistant

START_TIME = time.monotonic()
DEADLINE = START_TIME + config.TOTAL_BUDGET_SECONDS
ENHANCEMENT_TIME_MARGIN_SECONDS = 20  # don't start optional steps this close to the deadline

HUMOR_STYLES_FOR_POLISH = {"sarcastic", "humorous_tech", "humorous_non_tech"}


def time_remaining() -> float:
    return DEADLINE - time.monotonic()


def fallback_captions(styles) -> dict:
    return {s: "Caption unavailable due to a processing error for this clip." for s in styles}


def process_task(task: dict, gemini: GeminiCaptioner, gemma: GemmaAssistant) -> dict:
    task_id = task.get("task_id", "unknown")
    video_url = task.get("video_url")
    styles = task.get("styles") or sorted(config.REQUIRED_STYLES)
    local_path = None

    try:
        local_path = download_video(video_url)

        base_captions = gemini.caption_clip(local_path, styles)
        scene = gemini.scene_hint(base_captions)

        final_captions = {}
        for style, caption in base_captions.items():
            result = caption

            if (
                config.ENABLE_GEMMA_POLISH
                and gemma.available
                and style in HUMOR_STYLES_FOR_POLISH
                and time_remaining() > ENHANCEMENT_TIME_MARGIN_SECONDS
            ):
                result = gemma.polish(style, scene, result)

            if config.ENABLE_SELF_CRITIQUE and gemma.available:
                for _ in range(config.MAX_CRITIQUE_RETRIES):
                    if time_remaining() <= ENHANCEMENT_TIME_MARGIN_SECONDS:
                        break
                    score, feedback = gemma.judge(style, scene, result)
                    if score >= config.CRITIQUE_PASS_THRESHOLD:
                        break
                    hint = f"{result} (reviewer feedback to address: {feedback})" if feedback else result
                    result = gemma.polish(style, scene, hint)

            final_captions[style] = result or caption

        return {"task_id": task_id, "captions": final_captions}

    except Exception as e:
        print(f"[error] task {task_id} failed: {e}")
        traceback.print_exc()
        return {"task_id": task_id, "captions": fallback_captions(styles)}

    finally:
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass


def main():
    print(f"[*] Reading tasks from {config.INPUT_PATH}")
    with open(config.INPUT_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    gemini = GeminiCaptioner()
    gemma = GemmaAssistant()
    if not gemma.available:
        print("[!] FIREWORKS_API_KEY not set — running Gemini-only, no Gemma polish/critique.")

    results = []
    with ThreadPoolExecutor(max_workers=config.CONCURRENCY) as pool:
        futures = {pool.submit(process_task, task, gemini, gemma): task for task in tasks}
        for future in as_completed(futures):
            task = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                # Should be unreachable (process_task already catches everything),
                # but guarantee every task still produces an output row.
                styles = task.get("styles") or sorted(config.REQUIRED_STYLES)
                print(f"[error] unexpected failure for task {task.get('task_id')}: {e}")
                results.append({"task_id": task.get("task_id", "unknown"), "captions": fallback_captions(styles)})

    # Preserve original task order in the output.
    order = {t.get("task_id"): i for i, t in enumerate(tasks)}
    results.sort(key=lambda r: order.get(r["task_id"], 0))

    os.makedirs(os.path.dirname(config.OUTPUT_PATH) or ".", exist_ok=True)
    with open(config.OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    elapsed = time.monotonic() - START_TIME
    print(f"[+] Wrote {len(results)} results to {config.OUTPUT_PATH} in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
