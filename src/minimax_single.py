"""
minimax_single caption engine — ONE multimodal call per clip returns all
four styles as a single JSON object. That call geometry is the shape both
0.91 board teams run on minimax-m3 (SwiftCap, VeloCap); layered on top are
the same kind of deterministic, code-only guards qwen_direct uses:

  call failed / JSON unparseable  -> transport retries inside _chat_with_retry
  caption missing or under 8 words (hard) or style_violations()/overlap/
    over-length (soft)            -> ONE stricter full-set retry at temp 0.5
                                     carrying the exact problem list
  style still hard-failing        -> per-style rescue via qwen_direct's
                                     board-proven single-style call (4 frames)
  everything failed               -> "" (main.py fills its never-empty fallback)

A soft problem that survives the retry is tolerated: a real, slightly-long
caption beats a generic fallback on both judge axes.
"""
import time
from typing import Callable, Dict, List, Tuple

import config
import qwen_direct
from fireworks_vision_client import (
    _extract_json,
    _probe_duration_seconds,
    extract_frames_b64,
)
from prompts import (
    MINIMAX_SINGLE_SYSTEM_PROMPT,
    build_minimax_single_prompt,
    sanitize_caption,
    style_violations,
)

# Same deadline discipline as qwen_direct: no optional calls this close to
# the global budget — an imperfect caption in hand beats a truncated run.
EXTRA_CALL_TIME_MARGIN_SECONDS = 25

MIN_CAPTION_WORDS = 8    # below this a caption is a hard failure (VeloCap rule)
MAX_CAPTION_WORDS = 45   # nag threshold over the asked 12-35; soft only
PAIR_OVERLAP_LIMIT = 0.75  # VeloCap's cross-style diversity guard


def _word_set(text: str) -> set:
    return {w.strip(".,!?;:\"'").lower() for w in text.split()} - {""}


def _pair_overlap(a: str, b: str) -> float:
    wa, wb = _word_set(a), _word_set(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _set_problems(styles: List[str], captions: Dict[str, str]) -> Tuple[list, list]:
    """(hard, notes): hard = styles whose caption is missing/too short to
    ship; notes = human-readable soft problems fed back on the retry."""
    hard, notes = [], []
    for s in styles:
        cap = (captions.get(s) or "").strip()
        if not cap or len(cap.split()) < MIN_CAPTION_WORDS:
            hard.append(s)
            continue
        for v in style_violations(s, cap):
            notes.append(f"{s}: {v}")
        if len(cap.split()) > MAX_CAPTION_WORDS:
            notes.append(f"{s}: too long — rewrite it in 12-35 words, keeping "
                         "the same facts and the same joke")
    present = [s for s in styles if s not in hard]
    for i in range(len(present)):
        for k in range(i + 1, len(present)):
            if _pair_overlap(captions[present[i]], captions[present[k]]) > PAIR_OVERLAP_LIMIT:
                notes.append(f"{present[i]} and {present[k]} read almost the same — "
                             "make them clearly different in wording and angle")
    return hard, notes


def _attempt(captioner, frames_b64: List[str], styles: List[str],
             temperature: float, extra_note: str = "") -> Dict[str, str]:
    """One full-set call -> {style: sanitized caption or ""}. Raises on
    transport/JSON failure (caller decides what survives)."""
    content = [{"type": "text",
                "text": build_minimax_single_prompt(styles, len(frames_b64), extra_note)}]
    content += [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        for b64 in frames_b64
    ]
    raw = captioner._chat_with_retry(
        messages=[
            {"role": "system", "content": MINIMAX_SINGLE_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        model=config.MINIMAX_SINGLE_MODEL,
        max_tokens=config.MINIMAX_SINGLE_MAX_TOKENS,
        response_format={"type": "json_object"},
        temperature=temperature,
        timeout_seconds=config.MINIMAX_SINGLE_TIMEOUT_SECONDS,
        attempts=3,
    )
    obj = _extract_json(raw)
    # Key normalization (UniKL trick): "Humorous-Tech"/"humorous tech" would
    # otherwise silently drop a style.
    normalized = {
        str(k).strip().lower().replace("-", "_").replace(" ", "_"): v
        for k, v in obj.items()
    }
    return {s: sanitize_caption(str(normalized.get(s, ""))) for s in styles}


def caption_clip_minimax_single(captioner, ensure_downloaded: Callable[[], str],
                                styles: List[str],
                                time_remaining: Callable[[], float]) -> Dict[str, str]:
    """All requested styles for one clip in ONE call (+ guards). A single
    style's failure returns "" for that style only; raises only when the
    frames stage itself fails (caller falls back for the whole clip)."""
    local_path = ensure_downloaded()
    t0 = time.monotonic()
    duration = _probe_duration_seconds(local_path)
    n_frames = max(config.MINIMAX_SINGLE_MIN_FRAMES,
                   min(config.MINIMAX_SINGLE_MAX_FRAMES,
                       int(round(duration / config.MINIMAX_SINGLE_SECONDS_PER_FRAME))))
    frames_b64 = extract_frames_b64(local_path, n_frames,
                                    config.MINIMAX_SINGLE_FRAME_MAX_WIDTH)
    print(f"[minimax-single] {len(frames_b64)} frames "
          f"@{config.MINIMAX_SINGLE_FRAME_MAX_WIDTH}px in {time.monotonic() - t0:.2f}s")

    def clock_allows() -> bool:
        return time_remaining() > EXTRA_CALL_TIME_MARGIN_SECONDS

    captions: Dict[str, str] = {}
    try:
        captions = _attempt(captioner, frames_b64, styles,
                            config.MINIMAX_SINGLE_TEMPERATURE)
    except Exception as e:
        print(f"[minimax-single] primary call failed ({e})")

    hard, notes = _set_problems(styles, captions)

    # ONE stricter retry carrying the exact problem list. Kept only if it
    # fixes everything, or at least ships strictly fewer hard failures.
    if (hard or notes) and clock_allows():
        problems = [f"the '{s}' caption was missing or under {MIN_CAPTION_WORDS} words"
                    for s in hard] + notes
        feedback = ("Your previous JSON reply had these problems: "
                    + "; ".join(problems)
                    + " — fix exactly these and return the corrected JSON "
                    "object with every requested style.")
        print(f"[minimax-single] retrying once ({'; '.join(problems)[:200]})")
        try:
            retry = _attempt(captioner, frames_b64, styles, 0.5, extra_note=feedback)
            r_hard, r_notes = _set_problems(styles, retry)
            if (not r_hard and not r_notes) or len(r_hard) < len(hard):
                captions, hard = retry, r_hard
        except Exception as e:
            print(f"[minimax-single] retry failed ({e}) — keeping first result")

    # Per-style rescue on a different geometry AND different model family:
    # qwen_direct's board-proven single-style call on 4 subsampled frames.
    if hard and clock_allows():
        step = max(1, len(frames_b64) // 4)
        frames4 = frames_b64[::step][:4]
        for s in hard:
            if not clock_allows():
                break
            try:
                print(f"[minimax-single] {s}: rescuing via qwen_direct single-style call")
                rescued = qwen_direct._caption_one_style(captioner, frames4, s,
                                                         time_remaining)
                if rescued:
                    captions[s] = rescued
            except Exception as e:
                print(f"[minimax-single] {s}: rescue failed ({e})")

    return captions
