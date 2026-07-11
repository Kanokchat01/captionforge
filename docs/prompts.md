# 🎬 Video Captioning Prompts — AMD Hackathon Track 2

## Pipeline Flow

```
Video + Prompt 1 → Scene Report → Prompt 2 → 4 Captions (JSON)
```

---

## Prompt 1 — Video Analysis

> ส่งพร้อมวิดีโอเข้า Gemini 2.5 Flash

```text
You are a professional video analyst. Watch this video carefully — frame by frame, beginning to end — and produce a structured Scene Report.

If the video cannot be analyzed (corrupted, blank, no visual content, or fails to load), write only: "ANALYSIS FAILED: [brief reason]" and stop. Do not guess or invent content for a video you cannot actually see.

Pay close attention to: visual details (including fine-grained objects like messy/cluttered wiring, specific shapes or designs of lamps, furniture style, desk layout, and other prominent background/environment items), actions, timing, camera work, lighting, mood, and any audio (speech, music, ambient sound). If the video is silent, note that explicitly.

Keep each section concise — 2-4 sentences, except Key Actions and Standout Details which may use short bullet points. Avoid padding with generic description.

Write your report in the following 10 sections:

--- SCENE REPORT ---

1. SUBJECT
Who or what is the main focus? Describe appearance in detail (species, color, size, clothing, expression, distinguishing features).

2. ENVIRONMENT
Where does this take place? Describe the setting, surfaces, objects, background elements (specifically looking for details like cluttered power cables, specific shapes/types of lamps, wall decorations, furniture layout), weather, and time of day.

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
List 3-5 specific, quirky, or memorable details (e.g., a messy web of cords under the desk, a circular desk lamp, a distinct patterned wall) that make this video unique. Prioritize concrete physical details and fine-grained visual features that ground the scene in reality. These are the best ingredients for humor and captions.
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
```

### แต่ละ Section ทำหน้าที่อะไร

| Section | ป้อนข้อมูลให้ |
|---------|-------------|
| 1-7 (Subject → Mood) | → **Formal** caption (ทำคะแนน Accuracy) |
| 8-9 (Standout + Humor) | → **Sarcastic / Humorous** captions (วัตถุดิบมุก) |
| 10 (Risks) | → กัน **Hallucination** ทุก style |

---

## Prompt 2 — Caption Generation

> ทำงานบนผลลัพธ์ของ Prompt 1 (ไม่ต้องส่งวิดีโอซ้ำ)

```text
Using ONLY the previous video analysis report, generate 4 captions.

If the video analysis lacks sufficient detail for a style's word count, write a shorter, purely factual caption instead of inventing content to fill the length.

Rules:
- Write like a real person posting on social media, NOT like AI or a textbook.
- Use strong, specific verbs that match what's actually happening in THIS video (examples only, do not default to these every time: chase, navigate, glow, speed-run — vary your verb choice based on the actual footage).
- Use alliteration ONLY if it fits naturally and doesn't force inaccurate wording (e.g. "fluffy feline"). Never sacrifice accuracy for wordplay. If nothing fits naturally, skip it.
- No inner double quotes. Use single quotes if needed.
- No questions, no hashtags, no call-to-action, no markdown.
- Before finalizing, count the words in each caption and confirm it fits the required range for that style.

Grounding: Every claim must come from the video analysis report. Check the RISKS section of the report — do not include anything flagged there as uncertain or unconfirmed.

BANNED WORDS (never use — they sound like AI):
thoroughfare, bustling, captivating, witnessing, observing, commences, showcases, delves, furthermore, utilizing, vibrant, pivotal, intricate, landscape, tapestry, multifaceted, underscores, endeavor, realm

WRONG vs RIGHT:
❌ "An urban thoroughfare bustles with continuous vehicle movement"
✅ "A steady stream of cars flows down a wide city road"
❌ "Witnessing the captivating, never-ending urban grind"
✅ "Just another day of cars pretending they have somewhere important to be"
❌ "Observing the city's CI/CD pipeline in full swing"
✅ "This traffic has zero throughput and maximum latency"
❌ "The feline is observed navigating through the verdant foliage"
✅ "This cat treats the garden like its personal jungle gym"

Styles:

1. FORMAL (25-35 words): Professional, factual, objective. Incorporate specific, fine-grained details of the scene (e.g., cluttered cables, distinct lamp shapes, or environment layout) along with key actions. Use clear simple English a news anchor would say. No slang. No emojis. Do not start with "The scene shows" or "The video captures." Do not end with a generic summary sentence.

2. SARCASTIC (15-25 words): Write like texting a friend. Short sentences only, subject-verb-object order (e.g. "The kitten pounces" not "Pouncing is what the kitten does"). Never start with "Truly", "Such", "Witnessing", or "Behold". Actually mock something specific in the video. Use slang naturally (main character energy, aura points, cooked). End with a punchline + 1 emoji.

3. HUMOROUS_TECH (15-25 words): Pick ONE tech concept and connect it to what is actually happening in the video. Do not list multiple tech concepts. Punchy, one core joke. 1 emoji.

4. HUMOROUS_NON_TECH (15-25 words): Start with "POV:", "When you", "Me trying to", or "That feeling when". Write a situation everyone has experienced. Keep it simple and relatable. 1 emoji matching video content.

Output JSON only:
{
  "formal": "...",
  "sarcastic": "...",
  "humorous_tech": "...",
  "humorous_non_tech": "..."
}
```

### ความยาวแต่ละ Style

| Style | คำ | เหตุผล |
|-------|-----|--------|
| Formal | 25-35 | อธิบายฉากครบ → ทำคะแนน Accuracy |
| Sarcastic | 15-25 | ประชดต้องกระชับ ตบจบ |
| Humorous Tech | 15-25 | มุกไอทีสั้นคม |
| Humorous Non-Tech | 15-25 | มีมสั้นๆ ปังทันที |

---

## ตัวอย่างเปรียบเทียบ: ❌ กลิ่น AI vs ✅ ธรรมชาติ

> คลิป: ถนนในเมือง รถวิ่ง ต้นไม้ใบเหลือง ตึกอพาร์ตเมนต์

### ❌ ก่อนปรับ (ภาษา AI)

```json
{
  "formal": "An urban thoroughfare bustles with continuous vehicle movement under clear, sunny skies. Vibrant yellow autumn foliage lines the multi-lane road, contrasting with the towering apartment complexes that define the cityscape.",
  "sarcastic": "Witnessing the captivating, never-ending urban grind. This traffic is truly serving some 'main character' energy, completely cooked and ready for prime time. 🚦",
  "humorous_tech": "Observing the city's continuous integration and continuous deployment pipeline in full swing. Looks like someone forgot to optimize for latency, but the visual flow is epic. 💻",
  "humorous_non_tech": "POV: You're stuck in the endless daily commute, watching time itself blur past. These cars are in a constant, bustling race against the clock. 🚕"
}
```

**ปัญหา:** ศัพท์หรูเกิน (urban thoroughfare), ไม่ประชดจริง (Witnessing the captivating), แปะ IT มั่วๆ (CI/CD pipeline ไม่เกี่ยวกับรถ)

### ✅ หลังปรับ (ธรรมชาติ)

```json
{
  "formal": "A steady stream of vehicles moves along a multi-lane city road lined with golden autumn trees. Tall apartment buildings rise on both sides under a clear blue sky.",
  "sarcastic": "Just another day of cars pretending they have somewhere important to be. The autumn leaves are gorgeous though — too bad nobody stuck in traffic can enjoy them. 🍂",
  "humorous_tech": "This traffic has zero throughput and maximum latency. Someone deploy a load balancer on this road before the whole system crashes. 🚦",
  "humorous_non_tech": "POV: You finally leave early to beat traffic and somehow it's still bumper to bumper. The trees look amazing though, small wins. 🚗"
}
```

**ทำไมดีกว่า:** ภาษาตรงไปตรงมา, ประชดของจริง, มุก IT เชื่อมกับรถติดจริง, POV ที่คนทำงาน relate ได้

---

## กฎสำคัญ (Quick Reference)

| ✅ ทำ | ❌ ห้ามทำ |
|------|----------|
| เขียนเหมือนคนจริง | ใช้คำหรูแบบ AI (thoroughfare, captivating) |
| ใช้ powerful verbs (chase, glow, speed-run) | ใช้กริยาธรรมดา (walk, go, look) |
| จบด้วย punchline สั้นๆ | ถามคำถาม / Call-to-Action |
| อิงรายละเอียดจากวิดีโอจริง | แต่งเรื่อง / Hallucinate |
| ใช้สแลงที่ LLM เข้าใจ (locked in, peak cinema) | ใช้สแลงคลุมเครือ (delulu, nah) |
| Emoji 1 ตัว ตรงกับเนื้อหา | Emoji เยอะหรือไม่เกี่ยว |
