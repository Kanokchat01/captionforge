"""
CaptionForge — Track 2: Video Captioning Agent

Reads /input/tasks.json, for each task downloads the clip, generates one
caption per requested style with Gemini 2.5 Flash (native video+audio
understanding, 2-stage scene-report pipeline) — or, if
config.CAPTION_PROVIDER=fireworks_vision, an alternate frames-only path via
Fireworks (see fireworks_vision_client.py for why that path has no audio
understanding). Optionally polishes + self-critiques sarcastic/humor styles
via Gemma (Fireworks, own credentials) for the Gemma bonus prize, then
writes /output/results.json. Must exit 0, must finish within 10 minutes
total, must never crash the whole run because one clip failed, and must
never let one stuck task blow the whole container's time budget.
"""
import json
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait

from dotenv import load_dotenv

load_dotenv()  # no-op in the real submission container (no .env bundled); used for local dev

import config
from downloader import download_video, probe_size_mb
from gemini_client import GeminiCaptioner
from gemma_polish import GemmaAssistant

START_TIME = time.monotonic()
DEADLINE = START_TIME + config.TOTAL_BUDGET_SECONDS
ENHANCEMENT_TIME_MARGIN_SECONDS = 20  # don't start optional steps this close to the deadline
PROBE_PHASE_BUDGET_SECONDS = 20  # cap on how long the pre-sort probing pass may take

HUMOR_STYLES_FOR_POLISH = {"sarcastic", "humorous_tech", "humorous_non_tech"}


def make_captioner():
    """Picks the primary scene-understanding + caption engine based on
    config.CAPTION_PROVIDER. Both engines expose the same interface:
    caption_clip(video_path, styles) -> (captions: dict, scene_report: str).
    Default is "gemini" (native video+audio, proven/tested) — the
    "fireworks_vision" path is opt-in only (frames-only, no audio; see
    fireworks_vision_client.py's module docstring for why)."""
    if config.CAPTION_PROVIDER == "fireworks_vision":
        from fireworks_vision_client import FireworksCaptioner
        print("[*] CAPTION_PROVIDER=fireworks_vision — using Fireworks frame-based "
              "analysis (no audio understanding on this path).")
        return FireworksCaptioner()
    return GeminiCaptioner()


def time_remaining() -> float:
    return DEADLINE - time.monotonic()


def fallback_captions(styles, reason: str = "processing error") -> dict:
    return {s: f"Caption unavailable due to a {reason} for this clip." for s in styles}


def order_tasks_heaviest_first(tasks: list) -> list:
    """Probe each clip's size via a cheap HEAD request (in parallel, bounded
    time) so we can process the heaviest/slowest-looking clips first. This
    avoids a scenario where a large 4K clip ends up last in the queue right
    as the global time budget runs out. Unknown-size clips keep their
    relative order and are treated as weight 0 (not prioritized, not
    penalized)."""
    if not tasks:
        return tasks

    weights = {}
    with ThreadPoolExecutor(max_workers=min(config.CONCURRENCY, len(tasks))) as probe_pool:
        futures = {
            probe_pool.submit(probe_size_mb, t.get("video_url", "")): t.get("task_id")
            for t in tasks
        }
        done, not_done = futures_wait(futures.keys(), timeout=PROBE_PHASE_BUDGET_SECONDS)
        for f in done:
            task_id = futures[f]
            try:
                weights[task_id] = f.result() or 0.0
            except Exception:
                weights[task_id] = 0.0
        for f in not_done:
            weights[futures[f]] = 0.0  # didn't finish probing in time — treat as unknown

    return sorted(tasks, key=lambda t: weights.get(t.get("task_id"), 0.0), reverse=True)


def process_task(task: dict, captioner, gemma: GemmaAssistant) -> dict:
    task_id = task.get("task_id", "unknown")
    video_url = task.get("video_url")
    styles = task.get("styles") or sorted(config.REQUIRED_STYLES)
    local_path = None

    # Don't start new expensive work if the global clock is already too low
    # to safely attempt it — go straight to a fallback instead of getting
    # stuck partway through and eating into other tasks' time.
    if time_remaining() <= config.CRITICAL_TIME_THRESHOLD_SECONDS:
        print(f"[skip] task {task_id}: critical time remaining, using fallback without attempting analysis")
        return {"task_id": task_id, "captions": fallback_captions(styles, "time budget cutoff")}

    try:
        local_path = download_video(video_url)

        # caption_clip runs the 2-stage pipeline (scene report -> captions)
        # and returns the scene report alongside the captions. Do NOT store
        # this on the shared captioner instance — it's reused across worker
        # threads, so per-call state must stay local to this call.
        base_captions, scene = captioner.caption_clip(local_path, styles)

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

    captioner = make_captioner()
    gemma = GemmaAssistant()
    if not gemma.available:
        print("[!] FIREWORKS_API_KEY not set — running caption-engine-only, no Gemma polish/critique.")

    # Preserve the original input order for the final output — scheduling
    # order (heaviest-first) is only used to decide processing sequence.
    original_order = {t.get("task_id"): i for i, t in enumerate(tasks)}

    print(f"[*] Probing {len(tasks)} clip(s) to schedule heaviest first...")
    scheduled_tasks = order_tasks_heaviest_first(tasks)

    results_by_id = {}

    pool = ThreadPoolExecutor(max_workers=config.CONCURRENCY)
    futures = {pool.submit(process_task, task, captioner, gemma): task for task in scheduled_tasks}

    # Hard rule: never wait past the global deadline (minus a finalization
    # reserve) no matter how many tasks are still running. A single stuck
    # clip must not cost us every other clip's result.
    wait_budget = max(0.0, time_remaining() - config.FINALIZATION_RESERVE_SECONDS)
    done, not_done = futures_wait(futures.keys(), timeout=wait_budget)

    for f in done:
        task = futures[f]
        try:
            results_by_id[task.get("task_id")] = f.result()
        except Exception as e:
            styles = task.get("styles") or sorted(config.REQUIRED_STYLES)
            print(f"[error] unexpected failure for task {task.get('task_id')}: {e}")
            results_by_id[task.get("task_id")] = {"task_id": task.get("task_id", "unknown"), "captions": fallback_captions(styles)}

    for f in not_done:
        task = futures[f]
        task_id = task.get("task_id", "unknown")
        styles = task.get("styles") or sorted(config.REQUIRED_STYLES)
        print(f"[timeout] task {task_id} did not finish before the global deadline — using fallback")
        results_by_id[task_id] = {"task_id": task_id, "captions": fallback_captions(styles, "runtime budget timeout")}
        try:
            f.cancel()  # best-effort only; a running thread can't actually be killed
        except Exception:
            pass

    # Guarantee every input task_id produced a row, even if something above
    # was skipped entirely.
    for t in tasks:
        tid = t.get("task_id", "unknown")
        if tid not in results_by_id:
            styles = t.get("styles") or sorted(config.REQUIRED_STYLES)
            results_by_id[tid] = {"task_id": tid, "captions": fallback_captions(styles)}

    results = [results_by_id[t.get("task_id", "unknown")] for t in tasks]
    results.sort(key=lambda r: original_order.get(r["task_id"], 0))

    os.makedirs(os.path.dirname(config.OUTPUT_PATH) or ".", exist_ok=True)
    with open(config.OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    elapsed = time.monotonic() - START_TIME
    print(f"[+] Wrote {len(results)} results to {config.OUTPUT_PATH} in {elapsed:.1f}s "
          f"({len(not_done)} timed out)")

    sys.stdout.flush()
    sys.stderr.flush()
    # Force immediate process exit instead of letting the interpreter join
    # any still-running (possibly network-hung) worker threads — those
    # threads are non-daemon by default and would otherwise block process
    # exit indefinitely, risking the 10-minute hard limit even though valid
    # output has already been written.
    os._exit(0)


if __name__ == "__main__":
    main()
