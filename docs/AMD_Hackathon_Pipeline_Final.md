# AMD Hackathon Track 2 - Pipeline Final (Production / Hackathon Ready)

## Objectives

-   Complete within 10 minutes
-   Docker compatible
-   Stable under API failures
-   High caption quality
-   Produce valid `/output/results.json`
-   Exit with code 0

## Final Pipeline

``` text
Read tasks.json
        │
Download Video
        │
FFmpeg
├── Extract Audio
├── Extract Key Frames (3–5)
└── Lightweight Scene Detection (Max 3 Scenes)
        │
Gemini 2.5 Flash
(Vision + Audio Analysis)
        │
Object Memory Builder
        │
Rich Scene Description
        │
Context Reasoning
        │
Generate 4 Captions
        │
Caption Diversity Check
        │
Gemma Refinement
        │
Quality Evaluation
(Max 1 Retry)
        │
JSON Schema Validation
        │
Fallback Handler
        │
Write results.json
        │
Exit Code 0
```

## Core Components

### 1. Download Manager

-   Download each video once
-   Retry on network failure
-   Cache during development

### 2. FFmpeg Preprocessing

-   Extract audio
-   Extract 3--5 representative key frames
-   Lightweight scene detection (maximum 3 scenes)

### 3. Gemini 2.5 Flash

Single multimodal request: - Vision understanding - Audio
understanding - Event timeline - Emotion - Context

### 4. Object Memory

Store important entities across scenes.

``` python
object_memory = {
    "people": [],
    "objects": [],
    "actions": [],
    "locations": [],
    "emotions": []
}
```

### 5. Rich Scene Description

Merge: - Vision - Audio - Context - Objects - Timeline

into one structured description.

### 6. Context Reasoning

Determine: - Main event - Main character - Overall emotion - Funny
moments - Important objects

before caption generation.

### 7. Caption Generation

Generate: - Formal - Sarcastic - Humorous Tech - Humorous Non-Tech

### 8. Caption Diversity Check

Reject captions that are too similar. Use lightweight similarity
(e.g. difflib) instead of heavy embedding models.

### 9. Gemma Refinement

Improve: - Grammar - Natural wording - Humor - Tone consistency

### 10. Quality Evaluation

Evaluate: - Relevance - Humor - Creativity - Clarity - Style Match

Only one retry if quality is below threshold.

### 11. JSON Validation

Validate schema using Pydantic before writing results.

### 12. Retry & Timeout

-   Retry failed API calls
-   Timeout each request
-   Skip safely if necessary

### 13. Fallback Handler

Gemini → Retry → Retry → Template Caption

Always produce output.

### 14. Resource Cleanup

Delete: - Video - Audio - Frames after each task.

### 15. Logging

Record: - Download - API - Processing - Errors - Runtime

## Features Included

-   Download Manager
-   Retry Manager
-   Timeout Controller
-   FFmpeg Audio Extraction
-   Key Frame Extraction
-   Lightweight Scene Detection
-   Gemini Vision + Audio
-   Object Memory
-   Rich Scene Description
-   Context Reasoning
-   Caption Generation
-   Caption Diversity Check
-   Gemma Refinement
-   Quality Evaluation
-   JSON Validation
-   Logging
-   Resource Cleanup
-   API Rate Limiting
-   Fallback Mode

## Excluded by Design

-   Full scene splitting
-   Local Whisper
-   Local LLM
-   Sentence Transformers
-   Large embedding models
-   High-concurrency processing

## Recommended Parallelism

-   2--3 workers maximum
-   Respect Gemini rate limits
-   Pipeline overlap:
    -   Download next video
    -   Process current video
    -   Cleanup previous task

## Expected Benefits

-   Higher caption quality
-   Better humor consistency
-   Lower hallucination
-   Faster execution
-   Stable Docker execution
-   Better chance of completing all tasks within competition limits
