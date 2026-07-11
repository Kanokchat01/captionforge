# AMD Hackathon Track 2 - Final System Design (Version 3.1)

> Update from v3.0: added runtime-budget-aware scheduling for variable video duration (30 seconds to 2 minutes), dynamic work-stealing, adaptive degradation, and retry control under a 10-minute total runtime budget.

# Executive Summary

This architecture is optimized for the AMD Hackathon constraints:

- Runtime ≤ 10 minutes total for 12 hidden videos
- Docker-first deployment
- Stable under API failures
- High caption quality
- Reduced hallucination through grounded reasoning
- Always produce a valid `/output/results.json`

The main new risk addressed in this version is **variable video duration**. Hidden videos may range from 30 seconds to 2 minutes. Duration does not map perfectly to processing time, but longer clips usually increase download size, FFmpeg work, audio/context volume, token usage, and Gemini latency. Therefore, the system must not rely on average time per video. It must actively manage the global 10-minute budget.

# End-to-End Pipeline

``` text
Read tasks.json
      │
Global Runtime Controller
├─ Start timer
├─ Reserve finalization time
└─ Select processing mode by remaining budget
      │
Download + Probe Manager
├─ Download once
├─ ffprobe duration / size
└─ Estimate task weight
      │
Dynamic Work-Stealing Queue
├─ Prioritize heavier clips first when known
└─ Workers pull next task only if budget allows
      │
FFmpeg
├─ Audio Extraction
├─ Key Frames (adaptive 2-5)
└─ Lightweight Scene Detection (adaptive max 0-3)
      │
Gemini 2.5 Flash (Vision + Audio)
      │
Object Memory
      │
Rich Scene Description
      │
Context Reasoning
      │
Generate 4 Caption Styles
      │
Grounding Check
      │
Caption Diversity Check
      │
Optional Gemma Refinement
      │
Optional Quality Evaluation / Retry
      │
JSON Schema Validation
      │
Budget-Aware Retry / Timeout Manager
      │
Fallback Handler
      │
Logging + Cleanup
      │
Write results.json
      │
Exit Code 0
```

# Core Design

## Preprocessing

-   Download once
-   Extract audio
-   Extract only 3--5 representative key frames
-   Detect at most 3 scenes for speed

## Multimodal Analysis

One Gemini request combines: - Vision - Audio - Context - Timeline -
Emotion

## Object Memory

Stores people, objects, actions, locations, emotions and timeline.
Captions must reference this memory instead of inventing facts.

## Context Reasoning

Before caption generation the system identifies: - Main event - Main
subject - Scene emotion - Important objects - Potential humor
opportunities

## Grounding Check

Every caption is compared against the scene description.

Rules: - No new objects - No new actions - No fake dialogue - No
unsupported locations

If unsupported content exists, regenerate once.

## Caption Diversity

Ensure Formal, Sarcastic, Humorous-Tech and Humorous-NonTech are
structurally different using lightweight similarity checking.

## Gemma Refinement

Improve wording, grammar, tone and humor while preserving facts.

## Quality Evaluation

Evaluate: - Relevance - Grounding - Style match - Creativity - Humor -
Clarity

Only one retry to preserve runtime.


# Runtime Budget Risk: Variable Video Duration

## Problem

The hidden set contains 12 videos, and all videos must be processed in one container run within 10 minutes. Each video can be 30 seconds to 2 minutes long. The exact mix is unknown before evaluation.

This is risky because video duration affects runtime through several indirect costs:

| Stage | Runtime impact |
|---|---|
| Download | Longer videos usually have larger files and higher download time. |
| FFmpeg extraction | Seeking and decoding can be slower on longer or higher bitrate files. |
| Gemini analysis | Longer audio/context and more scene changes can increase token usage and latency. |
| Retry | Retrying a long or content-dense video is much more expensive than retrying a short one. |
| Scheduling | Static assignment can overload one worker with long videos while other workers sit idle. |

Therefore, the system must be designed for **worst-case and mixed-case hidden sets**, not only the three public examples.

## Design Goal

Always finish with a valid `results.json` before the hard 10-minute limit, even when:

- all 12 clips are close to 2 minutes;
- clips are randomly mixed between short and long;
- short clips are visually dense or dialogue-heavy;
- Gemini has temporary timeout or rate-limit errors;
- some tasks must degrade to a faster mode or fallback.

# Runtime Budget Controller

## Global Budget

Use a hard wall-clock timer from the start of the container process.

Recommended internal budget:

| Budget item | Time |
|---|---:|
| Official hard limit | 600 sec |
| Safe stop for AI calls | ~520-540 sec |
| Reserved time for JSON validation, cleanup, and writing output | 30-45 sec |
| Emergency fallback window | final 45-60 sec |

The system should not start a new expensive Gemini call if the remaining time is too low to complete it safely.

## Adaptive Processing Modes

The pipeline should reduce work based on remaining budget.

| Mode | When used | Processing strategy |
|---|---|---|
| Normal | Enough time remains | 5 frames, max 3 scenes, audio, Gemini, optional Gemma, quality check, one retry if needed. |
| Fast | Budget is moderate | 3 frames, max 1 scene, audio allowed, skip Gemma if Gemini output is valid. |
| Emergency | Budget is low | 2 frames, no scene detection, short audio/context only, no Gemma, no quality retry. |
| Fallback | Budget is critical or task failed | Template captions based on filename/basic visual extraction if available. |

This prevents one expensive clip from consuming the budget needed for the remaining clips.

# Dynamic Work-Stealing Scheduler

## Why not static assignment

Do not split 12 videos statically, such as 4 videos per worker. If one worker receives mostly 2-minute videos, that worker becomes the bottleneck while other workers finish early and wait.

## Recommended scheduling

Use a shared queue. Every worker repeatedly pulls the next available task from the queue. This creates natural work stealing: workers that finish short clips early immediately pick up more work.

If duration or file size is known after download/probe, sort heavier tasks first before putting them into the processing queue. This is similar to longest-processing-time-first scheduling and reduces the chance that a long clip is left until the end.

Recommended priority score:

```text
estimated_weight = duration_seconds * 1.0 + file_size_mb * 0.2 + scene_hint * 5
```

If scene_hint is unavailable, use only duration and file size.

# Budget-Aware Retry Policy

Retries must depend on remaining global time, not only a fixed retry count.

Rules:

1. Retry only recoverable failures: timeout, temporary API failure, rate limit, invalid JSON repair failure.
2. Do not retry if remaining time is below the required reserve.
3. Use bounded backoff. Never allow exponential backoff to grow without checking the global deadline.
4. Retry in a cheaper mode. Example: if Normal mode times out, retry once in Fast or Emergency mode.
5. Never let one clip retry repeatedly while unprocessed clips remain.

Suggested rule:

```text
allow_retry = remaining_time > finalization_reserve + estimated_min_time_for_remaining_tasks + retry_cost
```

# Budget-Aware Watchdog

The watchdog should not blindly kill all workers at the same cutoff. It should make stage-aware decisions.

## Task stages

Track each video state:

- queued
- downloading
- probing
- preprocessing
- gemini_call
- refining
- validating
- done
- fallback_done

## Cutoff behavior

When remaining time is low:

- Do not start new expensive AI calls.
- Let tasks in cheap final stages finish if they are close to completion.
- Cancel queued or not-yet-started expensive tasks and write fallback captions.
- If a worker is stuck inside an API call, enforce per-call timeout and then fallback.
- Always reserve enough time to write valid `results.json`.

This avoids losing a clip that is nearly done while another worker has just started a long expensive task.

# Implementation Blueprint

Below is a simplified Python-style blueprint for the scheduler.

```python
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum

TOTAL_BUDGET = 600
SAFE_AI_STOP = 535
FINALIZATION_RESERVE = 40
MAX_WORKERS = 3

class Mode(str, Enum):
    NORMAL = "normal"
    FAST = "fast"
    EMERGENCY = "emergency"
    FALLBACK = "fallback"

@dataclass(order=True)
class PrioritizedTask:
    # negative score so PriorityQueue pops heavier clips first
    priority: float
    video_id: str = field(compare=False)
    url: str = field(compare=False)
    duration: float = field(default=60.0, compare=False)
    size_mb: float = field(default=0.0, compare=False)

class RuntimeController:
    def __init__(self):
        self.start = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.start

    def remaining(self) -> float:
        return TOTAL_BUDGET - self.elapsed()

    def mode(self) -> Mode:
        r = self.remaining()
        if r <= FINALIZATION_RESERVE:
            return Mode.FALLBACK
        if r <= 90:
            return Mode.EMERGENCY
        if r <= 180:
            return Mode.FAST
        return Mode.NORMAL

    def can_start_ai_call(self, estimated_call_time: float = 35) -> bool:
        return self.elapsed() + estimated_call_time < SAFE_AI_STOP

    def can_retry(self, unprocessed_count: int, retry_cost: float = 25) -> bool:
        reserve_for_remaining = unprocessed_count * 12
        return self.remaining() > FINALIZATION_RESERVE + reserve_for_remaining + retry_cost

async def worker(name, queue, results, controller):
    while not queue.empty():
        task = await queue.get()
        current_mode = controller.mode()

        if current_mode == Mode.FALLBACK:
            results[task.video_id] = make_fallback(task.video_id)
            queue.task_done()
            continue

        try:
            results[task.video_id] = await process_one_video(
                task,
                mode=current_mode,
                controller=controller,
                timeout=min(70, max(15, controller.remaining() - FINALIZATION_RESERVE))
            )
        except Exception:
            unprocessed = queue.qsize()
            if controller.can_retry(unprocessed_count=unprocessed):
                try:
                    cheaper_mode = Mode.FAST if current_mode == Mode.NORMAL else Mode.EMERGENCY
                    results[task.video_id] = await process_one_video(
                        task,
                        mode=cheaper_mode,
                        controller=controller,
                        timeout=min(45, max(10, controller.remaining() - FINALIZATION_RESERVE))
                    )
                except Exception:
                    results[task.video_id] = make_fallback(task.video_id)
            else:
                results[task.video_id] = make_fallback(task.video_id)
        finally:
            cleanup_temp_files(task.video_id)
            queue.task_done()

async def run_all(tasks):
    controller = RuntimeController()
    results = {}
    queue = asyncio.PriorityQueue()

    for task in tasks:
        # Probe duration/file size if available. Heavier tasks go first.
        weight = task.duration * 1.0 + task.size_mb * 0.2
        await queue.put(PrioritizedTask(-weight, task.video_id, task.url, task.duration, task.size_mb))

    workers = [
        asyncio.create_task(worker(f"worker-{i}", queue, results, controller))
        for i in range(MAX_WORKERS)
    ]

    await queue.join()

    for w in workers:
        w.cancel()

    # Fill missing outputs defensively.
    for task in tasks:
        if task.video_id not in results:
            results[task.video_id] = make_fallback(task.video_id)

    validate_and_write_results(results)
```

# Required Tests for This Risk

Add these tests before final submission:

| Test | Purpose |
|---|---|
| 12 clips x 2 minutes | Worst-case duration budget. |
| 6 short + 6 long shuffled | Check dynamic scheduling and load balance. |
| 30-second dense montage | Check that short does not always mean cheap. |
| One long clip with forced Gemini timeout | Check retry budget and fallback. |
| Global time nearly exhausted | Ensure valid `results.json` is still written. |
| Worker imbalance simulation | Confirm no worker stays idle while work remains. |

# Acceptance Criteria

The runtime-budget solution is considered successful if:

- 12 videos always produce 12 result objects.
- `results.json` is valid even when several tasks fallback.
- Total runtime stays below 10 minutes with a safety margin.
- Workers use a shared queue, not static assignment.
- Retry decisions check remaining global time.
- Finalization time is reserved and never consumed by API retries.
- Long videos are not left until the end when duration/size is known.

# Reliability Strategy

- Retry API failures only when the remaining global budget allows it.
- Use request timeout per API call.
- Use bounded exponential backoff for rate limits.
- Use dynamic work-stealing queue instead of static worker assignment.
- Use adaptive processing modes: Normal, Fast, Emergency, Fallback.
- Reserve finalization time for schema validation, cleanup, and writing `results.json`.
- JSON schema validation.
- Resource cleanup after every task.
- Structured logging.
- Graceful exit.
- Fallback captions if AI services fail or budget becomes too low.

# Failure Handling

  Scenario                     Strategy
  ---------------------------- ------------------------------
  API timeout                  Retry then fallback
  Rate limit                   Exponential backoff
  Silent video                 Vision only
  Audio extraction failed      Continue with vision
  Scene detection failed       Analyze whole video
  Invalid JSON                 Repair then validate
  Gemini unavailable           Retry then template fallback
  Gemma unavailable            Skip refinement
  Temporary files accumulate   Cleanup immediately

# Performance Optimizations

- Max 3 scenes in Normal mode; reduce to 1 or 0 in Fast/Emergency mode.
- 3-5 key frames in Normal mode; reduce to 2-3 frames when budget is low.
- Max 2-3 workers, but use a shared dynamic queue rather than static assignment.
- Prioritize heavier clips first after probing duration/file size.
- Lightweight similarity (difflib).
- No local Whisper.
- No local LLM.
- No embedding models.
- Slim Docker image.
- Always keep a finalization reserve before the 10-minute hard limit.

# Testing Checklist

## Functional

-   Docker build
-   Docker run
-   Valid results.json
-   Exit code 0

## Reliability

-   Silent video
-   Dark video
-   Multiple scenes
-   API timeout
-   Network interruption
-   Invalid responses

## Performance

-   12 hidden videos
-   Runtime under 10 minutes
-   Stable memory usage
-   Temporary file cleanup

## Quality

-   Four distinct caption styles
-   Low hallucination
-   Grounded captions
-   Style consistency

# Competitive Advantages

1.  Multistage reasoning instead of direct caption generation.
2.  Object Memory maintains consistent context.
3.  Context Reasoning improves semantic understanding.
4.  Grounding Check reduces hallucination.
5.  Diversity Check ensures meaningful stylistic differences.
6.  Self quality evaluation before output.
7.  Production-grade reliability with retry, timeout and fallback.
8.  Optimized specifically for Docker and hackathon constraints.

# Known Limitations

- Hallucination cannot be eliminated completely.
- Humor remains subjective.
- API latency may vary.
- Hidden set runtime can still vary due to network speed, file bitrate, model latency, and rate limits.
- Emergency/Fallback mode may reduce caption quality, but it protects the submission from missing output or exceeding the hard runtime limit.

The system minimizes these risks through grounding, validation and
fallback mechanisms rather than assuming perfect model behavior.
