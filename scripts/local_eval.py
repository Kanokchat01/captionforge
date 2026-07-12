"""
Local proxy for the official Track 2 judge.

Scores a results.json against the official two-axis rubric — accuracy (0-1)
and style match (0-1) per caption — using TWO cross-family text judges
(glm-5p1 + deepseek-v4-pro, temp 0) whose scores are averaged. The judges
never see the video; the VERIFIED scene reports from build_reference.py act
as the accuracy ground truth (same method the 2026-07-11 model benchmark
used).

The absolute number is a proxy — its job is RELATIVE comparison between
pipeline variants. Calibrate once against a results file with a known
leaderboard score, then trust deltas.

Usage:
    python scripts/local_eval.py output/results_baseline.json
    python scripts/local_eval.py output/results_v2.json --tag v2-facts

Writes <results>.eval.json next to the input with per-caption details.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

# Windows consoles default to cp1252, which can't print emojis that may
# appear in judged captions — never let a print kill the report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

import config  # noqa: E402
from prompts import STYLE_DESCRIPTIONS  # noqa: E402

REFS_PATH = os.path.join(ROOT, "eval", "reference_reports.json")
JUDGE_MODELS = [
    "accounts/fireworks/models/glm-5p1",
    "accounts/fireworks/models/deepseek-v4-pro",
]
MAX_WORKERS = 8
STYLE_ORDER = ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]

EVAL_SYSTEM_PROMPT = (
    "You are the automated judge of a video-captioning contest. You are given "
    "the contest's official one-line definition of a caption style, a verified "
    "ground-truth scene report describing everything confirmed to be in the "
    "video, and one caption. Score the caption on the contest's two official "
    "axes, each 0.0-1.0 independently:\n"
    "- accuracy: every claim in the caption is supported by the scene report. "
    "Penalize heavily: claims that contradict the report, specific details "
    "(counts, colors, actions, objects) the report does not support, quoted "
    "on-screen text, or a named real-world city/country/landmark. Vague but "
    "consistent captions are accurate but a caption that correctly names "
    "several specific details from the report deserves a higher accuracy "
    "score than one generic enough to fit many different videos.\n"
    "- style_match: the caption genuinely lands the official style definition "
    "(tone, intent, and for humorous styles, whether it is actually funny "
    "about THIS scene rather than generic filler).\n"
    'Respond with ONLY a JSON object: {"accuracy": <0-1>, "style_match": <0-1>}'
)


def judge_once(model: str, style: str, reference: str, caption: str) -> dict:
    user = (
        f'Official style definition of "{style}": "{STYLE_DESCRIPTIONS[style]}"\n\n'
        f"Verified ground-truth scene report:\n{reference}\n\n"
        f"Caption to score:\n{caption}"
    )
    last_exc = None
    for _ in range(2):
        try:
            resp = requests.post(
                f"{config.FIREWORKS_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {config.FIREWORKS_API_KEY}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": EVAL_SYSTEM_PROMPT},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": 120,
                    "temperature": 0.0,
                    "reasoning_effort": "none",
                    "response_format": {"type": "json_object"},
                },
                timeout=45,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
            return {
                "accuracy": max(0.0, min(1.0, float(data["accuracy"]))),
                "style_match": max(0.0, min(1.0, float(data["style_match"]))),
            }
        except Exception as e:  # noqa: BLE001 — retry once, then surface
            last_exc = e
    raise RuntimeError(f"judge {model} failed twice: {last_exc}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", help="path to a results.json produced by the pipeline")
    ap.add_argument("--tag", default="", help="label stored in the eval output")
    args = ap.parse_args()

    with open(args.results, encoding="utf-8") as f:
        results = json.load(f)
    with open(REFS_PATH, encoding="utf-8") as f:
        refs = json.load(f)

    jobs = []  # (task_id, style, caption, reference)
    skipped = []
    for row in results:
        tid = row.get("task_id")
        ref = refs.get(tid, {}).get("verified_report")
        if not ref:
            skipped.append(tid)
            continue
        for style, caption in row.get("captions", {}).items():
            if style in STYLE_DESCRIPTIONS and caption:
                jobs.append((tid, style, caption, ref))
    if skipped:
        print(f"[eval] no reference report for: {', '.join(map(str, skipped))} — skipped")
    if not jobs:
        print("[eval] nothing to score")
        return 1

    def score(job):
        tid, style, caption, ref = job
        per_judge = {m.rsplit("/", 1)[-1]: judge_once(m, style, ref, caption) for m in JUDGE_MODELS}
        acc = sum(j["accuracy"] for j in per_judge.values()) / len(per_judge)
        sty = sum(j["style_match"] for j in per_judge.values()) / len(per_judge)
        return {"task_id": tid, "style": style, "caption": caption,
                "accuracy": acc, "style_match": sty, "score": (acc + sty) / 2,
                "judges": per_judge}

    print(f"[eval] scoring {len(jobs)} captions x {len(JUDGE_MODELS)} judges...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        scored = list(pool.map(score, jobs))

    # --- per-clip x per-style table ---
    by_task: dict = {}
    for s in scored:
        by_task.setdefault(s["task_id"], {})[s["style"]] = s
    styles = [st for st in STYLE_ORDER if any(st in v for v in by_task.values())]
    col = 18
    print("\n" + "clip".ljust(6) + "".join(st[:col - 2].ljust(col) for st in styles) + "mean")
    for tid in sorted(by_task):
        row_scores = []
        line = tid.ljust(6)
        for st in styles:
            s = by_task[tid].get(st)
            if s:
                line += f"a{s['accuracy']:.2f}/s{s['style_match']:.2f}".ljust(col)
                row_scores.append(s["score"])
            else:
                line += "-".ljust(col)
        line += f"{sum(row_scores) / len(row_scores):.3f}" if row_scores else "-"
        print(line)

    # --- aggregates ---
    print("\nper-style means:")
    for st in styles:
        ss = [s for s in scored if s["style"] == st]
        acc = sum(s["accuracy"] for s in ss) / len(ss)
        sty = sum(s["style_match"] for s in ss) / len(ss)
        print(f"  {st:<20} accuracy {acc:.3f}   style {sty:.3f}   combined {(acc + sty) / 2:.3f}")
    overall = sum(s["score"] for s in scored) / len(scored)
    overall_acc = sum(s["accuracy"] for s in scored) / len(scored)
    overall_sty = sum(s["style_match"] for s in scored) / len(scored)
    print(f"\nOVERALL: {overall:.4f}   (accuracy {overall_acc:.4f}, style {overall_sty:.4f}, "
          f"{len(scored)} captions)")

    # --- worst offenders, the actionable part ---
    print("\n5 weakest captions:")
    for s in sorted(scored, key=lambda x: x["score"])[:5]:
        print(f"  [{s['score']:.2f} a{s['accuracy']:.2f}/s{s['style_match']:.2f}] "
              f"{s['task_id']}/{s['style']}: {s['caption'][:110]}")

    out_path = args.results.rsplit(".", 1)[0] + ".eval.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"tag": args.tag, "overall": overall, "accuracy": overall_acc,
                   "style_match": overall_sty, "captions": scored}, f, indent=2, ensure_ascii=False)
    print(f"\n[eval] details written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
