"""
Prompt construction for the Track 2 Video Captioning Agent.

Two-stage pipeline (from the team's prompts.md):
  Stage 1: video + SCENE_ANALYSIS_PROMPT -> structured 10-section Scene Report
  Stage 2: Scene Report (text only, no video) + style rules -> 4 captions JSON

Style keys MUST match the official spec exactly (underscore, not hyphen):
formal, sarcastic, humorous_tech, humorous_non_tech
"""

# Short one-line descriptions, used for Gemma polish/judge prompts only.
STYLE_DESCRIPTIONS = {
    "formal": "Professional, objective, factual tone. No jokes, no slang.",
    "sarcastic": "Dry, ironic, lightly mocking tone — sarcasm must clearly "
                 "land and stay recognizable as commentary on this specific clip.",
    "humorous_tech": "Funny, with technology or programming references — "
                      "ground the joke in something actually visible/audible "
                      "in the clip, not a generic tech pun.",
    "humorous_non_tech": "Funny, everyday humor with no technical jargon — "
                          "broadly relatable, grounded in the actual clip content.",
}

# Full per-style generation rules used in Stage 2 (verbatim from the team's
# prompt design, word counts + structural rules + banned openings).
STYLE_RULES = {
    "formal": (
        'FORMAL (25-35 words): Professional, factual, objective. Use clear '
        'simple English a news anchor would say. No slang. No emojis. Do '
        'not start with "The scene shows" or "The video captures." Do not '
        'end with a generic summary sentence.'
    ),
    "sarcastic": (
        'SARCASTIC (15-25 words): Write like texting a friend. Short '
        'sentences only, subject-verb-object order (e.g. "The kitten '
        'pounces" not "Pouncing is what the kitten does"). Never start with '
        '"Truly", "Such", "Witnessing", or "Behold". Actually mock '
        'something specific in the video. Use slang naturally (main '
        'character energy, aura points, cooked). End with a punchline + 1 '
        'emoji.'
    ),
    "humorous_tech": (
        'HUMOROUS_TECH (15-25 words): Pick ONE tech concept and connect it '
        'to what is actually happening in the video. Do not list multiple '
        'tech concepts. Punchy, one core joke. 1 emoji.'
    ),
    "humorous_non_tech": (
        'HUMOROUS_NON_TECH (15-25 words): Rotated openings. Start strictly with '
        'one of these four phrases based on the scene context: "POV:", "When you", '
        '"Me trying to", or "That feeling when". Connect to highly relatable, everyday '
        'human struggles, social anxiety, work exhaustion, or awkward moments. Vary your '
        'scenarios dynamically depending on the video domain (e.g., exhaustion for sports, '
        'extreme hunger for food, social dread for interviews/news, rhythm tracking for music, '
        'or weather ruined plans). Never use a repetitive or generic formula. Keep it punchy. '
        'End with exactly 1 relevant emoji.'
    ),
}

SCENE_ANALYSIS_PROMPT = """You are a professional video analyst. Watch this video carefully — frame by frame, beginning to end — and produce a structured Scene Report.

If the video cannot be analyzed (corrupted, blank, no visual content, or fails to load), write only: "ANALYSIS FAILED: [brief reason]" and stop. Do not guess or invent content for a video you cannot actually see.

Pay close attention to: visual details, actions, timing, camera work, lighting, mood, and any audio (speech, music, ambient sound). If the video is silent, note that explicitly.

Keep each section concise — 2-4 sentences, except Key Actions and Standout Details which may use short bullet points. Avoid padding with generic description.

Write your report in the following 10 sections:

--- SCENE REPORT ---

1. SUBJECT
Who or what is the main focus? Describe appearance in detail (species, color, size, clothing, expression, distinguishing features).

2. ENVIRONMENT
Where does this take place? Describe the setting, surfaces, objects, background elements, weather, and time of day.

3. KEY ACTIONS (timeline)
List 3-6 key moments chronologically, prioritizing clear scene changes over minor movements. Use timestamps.
Format: [MM:SS - MM:SS] Action description
Example: [00:00 - 00:03] A kitten sits behind leafy branches, looking at the camera.

4. CAMERA & FRAMING
Describe the camera angle (low, high, eye-level), movement (pan, tilt, static, tracking), and any notable framing choices (close-up, wide shot, depth of field).

5. LIGHTING & COLOR
Describe the dominant light source, color palette, contrast, and any notable visual effects (lens flare, bokeh, golden hour glow, neon).

6. AUDIO
What do you hear? Categories: speech (transcribe key words), music (genre, tempo, mood), ambient sounds (nature, city, machinery), or silence.
If there is no audio track, or the video is silent, write exactly: "No audio present." Do not guess at implied or expected sounds.

7. MOOD & ATMOSPHERE
What emotion does the video evoke? (e.g., peaceful, chaotic, tense, heartwarming, eerie, comedic)

8. STANDOUT DETAILS
List 3-5 specific, quirky, or memorable details that make this video unique. These are the best ingredients for humor and captions.
Example: "The kitten's fur is backlit by sunlight, creating a golden halo effect."

9. HUMOR POTENTIAL
What is naturally funny, ironic, cute, dramatic, or absurd about this video? Think like a meme creator. Identify the 'comedy goldmine' moments.
Base this only on what is visually or audibly confirmed in sections 1-6 — not on assumed intent, thoughts, or emotions the subject cannot literally express. If a subject "looks annoyed," describe the visible expression, don't assert the subject IS annoyed.

10. RISKS (things NOT in the video)
List anything a caption writer might assume or hallucinate that is NOT actually shown. This prevents inaccurate captions.
Example: "No butterflies visible. No other animals. No human hands shown."

--- END REPORT ---

Important:
- Be specific, not generic. "Orange tabby kitten" not just "a cat."
- Describe what you actually SEE, not what you assume.
- If unsure about something, say "possibly" or "appears to be." Anything marked this way should be treated as unconfirmed, not fact.
"""


def build_frame_scene_analysis_prompt(frame_timestamps, video_duration):
    """Stage 1 prompt variant for the Fireworks frame-based path (no native
    video/audio call available — see config.CAPTION_PROVIDER comment). The
    model only receives N still frames as images, at the given timestamps,
    and NO audio at all (Fireworks' Whisper endpoints were confirmed
    discontinued as of 2026-06-10). Same 10-section report shape as
    SCENE_ANALYSIS_PROMPT so build_caption_generation_prompt (Stage 2) needs
    no changes at all — section 6 (AUDIO) is simply forced to "No audio
    present" instead of asking the model to guess at sound it never got."""
    ts_list = ", ".join("{:.1f}s".format(t) for t in frame_timestamps)
    header = (
        "You are a professional video analyst. You are given "
        + str(len(frame_timestamps))
        + " still frames sampled from a "
        + "{:.0f}".format(video_duration)
        + "-second video, in chronological order, taken at approximately "
        "these timestamps: " + ts_list + ". You do NOT have the audio "
        "track — do not guess at or invent any sound, dialogue, or music."
    )
    return header + """

If the frames cannot be analyzed (corrupted, blank, no visual content), write only: "ANALYSIS FAILED: [brief reason]" and stop. Do not guess or invent content you cannot actually see.

Pay close attention to: visual details, actions implied by how the scene changes between frames, camera work, lighting, and mood. Treat gaps between frames as unknown — do not invent what happened between them.

Keep each section concise — 2-4 sentences, except Key Actions and Standout Details which may use short bullet points. Avoid padding with generic description.

Write your report in the following 10 sections:

--- SCENE REPORT ---

1. SUBJECT
Who or what is the main focus? Describe appearance in detail (species, color, size, clothing, expression, distinguishing features).

2. ENVIRONMENT
Where does this take place? Describe the setting, surfaces, objects, background elements, weather, and time of day.

3. KEY ACTIONS (timeline)
List what changes across the sampled frames, chronologically, using the frame timestamps given above.
Format: [MM:SS] Action/description at that frame.
Example: [00:03] A kitten sits behind leafy branches, looking at the camera.

4. CAMERA & FRAMING
Describe the camera angle (low, high, eye-level) and framing (close-up, wide shot, depth of field) as seen across the frames. Only describe movement (pan/tilt/tracking) if it can be confidently inferred from how framing changes between frames — otherwise say "static or unknown."

5. LIGHTING & COLOR
Describe the dominant light source, color palette, contrast, and any notable visual effects (lens flare, bokeh, golden hour glow, neon).

6. AUDIO
No audio track was provided for analysis. Write exactly: "No audio present." Do not guess at implied or expected sounds.

7. MOOD & ATMOSPHERE
What emotion do the frames evoke? (e.g., peaceful, chaotic, tense, heartwarming, eerie, comedic)

8. STANDOUT DETAILS
List 3-5 specific, quirky, or memorable details that make this video unique. These are the best ingredients for humor and captions.
Example: "The kitten's fur is backlit by sunlight, creating a golden halo effect."

9. HUMOR POTENTIAL
What is naturally funny, ironic, cute, dramatic, or absurd about this video? Think like a meme creator. Identify the 'comedy goldmine' moments.
Base this only on what is visually confirmed in sections 1-5 — not on assumed intent, thoughts, or emotions the subject cannot literally express. If a subject "looks annoyed," describe the visible expression, don't assert the subject IS annoyed.

10. RISKS (things NOT confirmed)
List anything a caption writer might assume or hallucinate that is NOT actually shown across the sampled frames, including anything that might have happened in the gaps between frames, and note that no audio was available.
Example: "No butterflies visible. No other animals. No human hands shown. No audio track analyzed."

--- END REPORT ---

Important:
- Be specific, not generic. "Orange tabby kitten" not just "a cat."
- Describe what you actually SEE in these specific frames, not what you assume happens between them.
- If unsure about something, say "possibly" or "appears to be." Anything marked this way should be treated as unconfirmed, not fact.
"""


CAPTION_GENERATION_SHARED_RULES = """If the video analysis lacks sufficient detail for a style's word count, write a shorter, purely factual caption instead of inventing content to fill the length.

Rules:
- Write like a real person posting on social media, NOT like AI or a textbook.
- Use strong, specific verbs that match what's actually happening in THIS video (examples only, do not default to these every time: chase, navigate, glow, speed-run — vary your verb choice based on the actual footage).
- Use alliteration ONLY if it fits naturally and doesn't force inaccurate wording (e.g. "fluffy feline"). Never sacrifice accuracy for wordplay. If nothing fits naturally, skip it.
- No inner double quotes. Use single quotes if needed.
- No questions, no hashtags, no call-to-action, no markdown.
- Before finalizing, count the words in each caption and confirm it fits the required range for that style.

Grounding: Every claim must come from the video analysis report above. Check the RISKS section of the report — do not include anything flagged there as uncertain or unconfirmed.

BANNED WORDS (never use — they sound like AI):
thoroughfare, bustling, captivating, witnessing, observing, commences, showcases, delves, furthermore, utilizing, vibrant, pivotal, intricate, landscape, tapestry, multifaceted, underscores, endeavor, realm

WRONG vs RIGHT FOR HUMOROUS_NON_TECH (Dynamic Scenarios Based on Domain):
❌ "POV: When you get stuck in the bustling urban grid during rush hour"
✅ "When you get stuck in afternoon traffic and realize everyone else is also pretending to have somewhere important to be 🚗"
❌ "POV: When the feline navigates the green garden foliage"
✅ "POV: You open a bag of snacks as quietly as possible, but the local furry overlord still hears it from a mile away 🍗"
❌ "Me trying to see the beautiful landscape and mountains in the quiet nature"
✅ "That feeling when you escape to nature for some peace, but the absolute silence starts making you feel highly suspicious 🌲"
❌ "POV: Looking at the person playing musical instruments or reporting news"
✅ "Me trying to nod along to the complex jazz solo like I actually understand music theory 🎸"
❌ "When you watch the news reporter talk on television"
✅ "POV: The professor randomly calls your name to explain the reading material you did not even open 🎤"
❌ "Me trying to exercise or run on the sports field"
✅ "Me trying to finish the last set of squats when my legs are already acting like jelly 🏋️"
❌ "That feeling when you see delicious food on the table"
✅ "That feeling when the waiter passes your table with food, but it is actually for the person behind you 🍕"
"""


def build_caption_generation_prompt(scene_report: str, styles: list) -> str:
    """Stage 2 prompt: text-only, works purely from the Stage 1 Scene Report
    (no video re-attached — cheaper and faster than a second video call)."""
    style_blocks = "\n\n".join(STYLE_RULES.get(s, f"{s.upper()} (15-25 words): write in this requested style.") for s in styles)
    keys_example = ", ".join(f'"{s}": "..."' for s in styles)
    return f"""Using ONLY the following video analysis report, generate {len(styles)} caption(s).

--- VIDEO ANALYSIS REPORT ---
{scene_report}
--- END REPORT ---

{CAPTION_GENERATION_SHARED_RULES}

Styles required for this clip:

{style_blocks}

Output JSON only with exactly these keys: {{{keys_example}}}
"""


QWEN_POLISH_SYSTEM_PROMPT = (
    "You punch up captions for humor and technical/sarcastic wit, without "
    "changing the underlying facts. You are given the video's scene details "
    "and a draft caption. Rewrite it to be funnier and sharper in the same "
    "style, but keep it grounded in the same concrete details — do not "
    "invent new facts about the video, and do not make it longer than the "
    "original by more than ~30%. Return only the rewritten caption text, "
    "no preamble."
)


def build_qwen_polish_prompt(style: str, scene_hint: str, draft_caption: str) -> str:
    return (
        f"Style: {style} ({STYLE_DESCRIPTIONS.get(style, '')})\n"
        f"Scene details: {scene_hint}\n"
        f"Draft caption: {draft_caption}\n\n"
        "Rewrite it now, sharper and funnier, same style, same facts."
    )


JUDGE_SYSTEM_PROMPT = (
    "You are a strict judge scoring a video caption on a 0-10 scale for two "
    "things combined into one score: (a) accuracy — does it faithfully "
    "reflect the described scene, and (b) style match — does it genuinely "
    "match the requested tone rather than being generic. Respond with ONLY "
    "a JSON object: {\"score\": <0-10 number>, \"feedback\": \"<one short "
    "actionable sentence for how to improve it if score < 8>\"}."
)


def build_judge_prompt(style: str, scene_hint: str, caption: str) -> str:
    return (
        f"Requested style: {style} ({STYLE_DESCRIPTIONS.get(style, '')})\n"
        f"Scene details: {scene_hint}\n"
        f"Caption to judge: {caption}"
    )