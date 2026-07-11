# AMD Hackathon Track 2 - Final System Design (Version 3.0)

# Executive Summary

This architecture is optimized for the AMD Hackathon constraints: -
Runtime ≤ 10 minutes - Docker-first deployment - Stable under API
failures - High caption quality - Reduced hallucination through grounded
reasoning - Always produce a valid `/output/results.json`

# End-to-End Pipeline

``` text
Read tasks.json
      │
Download Manager
      │
FFmpeg
├─ Audio Extraction
├─ Key Frames (3-5)
└─ Lightweight Scene Detection (max 3)
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
Gemma Refinement
      │
Quality Evaluation (1 Retry Max)
      │
JSON Schema Validation
      │
Retry / Timeout Manager
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

# Reliability Strategy

-   Retry API failures
-   Request timeout
-   Exponential backoff for rate limits
-   JSON schema validation
-   Resource cleanup after every task
-   Structured logging
-   Graceful exit
-   Fallback captions if AI services fail

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

-   Max 3 scenes
-   3-5 key frames
-   Max 2-3 workers
-   Lightweight similarity (difflib)
-   No local Whisper
-   No local LLM
-   No embedding models
-   Slim Docker image

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

-   Hallucination cannot be eliminated completely.
-   Humor remains subjective.
-   API latency may vary.

The system minimizes these risks through grounding, validation and
fallback mechanisms rather than assuming perfect model behavior.
