"""
Prompt construction for the Track 2 Video Captioning Agent.

Style keys MUST match the official spec exactly (underscore, not hyphen):
formal, sarcastic, humorous_tech, humorous_non_tech
"""

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


def build_caption_prompt(styles: list[str]) -> str:
    """Ask Gemini to watch the whole video (it natively understands both
    the visual track and the audio track) and return one caption per
    requested style, grounded in concrete details actually seen/heard.
    Only ask for the styles this specific task requires."""
    style_lines = "\n".join(
        f'- "{s}": {STYLE_DESCRIPTIONS.get(s, "Write in this requested style.")}'
        for s in styles
    )
    keys_example = ", ".join(f'"{s}": "..."' for s in styles)
    return f"""Watch this video clip carefully, including both what is shown on screen
and anything said or heard in the audio. Then write ONE caption or short
summary (1-3 sentences) for each of the following styles. Ground every
caption in specific, concrete details you actually observed in this clip
(objects, actions, setting, people, sounds) — do not write generic captions
that could apply to any video.

Strict grounding rule: only reference things you can actually see or hear in
THIS clip. Do not invent or guess at off-screen content, thoughts, or
un-shown context (for example: do not claim to know what is on someone's
screen, what they are thinking, or what happens outside the frame) — jokes
must be built from what is literally visible/audible, not speculation about
things not shown.

Styles required for this clip:
{style_lines}

Return ONLY a JSON object with exactly these keys: {{{keys_example}}}
"""


GEMMA_POLISH_SYSTEM_PROMPT = (
    "You punch up captions for humor and technical/sarcastic wit, without "
    "changing the underlying facts. You are given the video's scene details "
    "and a draft caption. Rewrite it to be funnier and sharper in the same "
    "style, but keep it grounded in the same concrete details — do not "
    "invent new facts about the video, and do not make it longer than the "
    "original by more than ~30%. Return only the rewritten caption text, "
    "no preamble."
)


def build_gemma_polish_prompt(style: str, scene_hint: str, draft_caption: str) -> str:
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
