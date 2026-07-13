# การวิเคราะห์และเปรียบเทียบ Prompt: VeloCap vs CaptionForge
เอกสารฉบับนี้ทำการวิเคราะห์เชิงลึกเกี่ยวกับ **Prompt Engineering** และโครงสร้างการเรียกใช้งาน API (API Call Geometry) ระหว่าง **VeloCap** (คะแนน 0.91) และ **CaptionForge** (โครงการปัจจุบันของคุณ) เพื่อหาโอกาสในการเพิ่มประสิทธิภาพและปรับปรุงคะแนน

---

## 1. เปรียบเทียบโครงสร้าง API Call และสถาปัตยกรรม Prompt

| มิติการเปรียบเทียบ | VeloCap (0.91) | CaptionForge (ปัจจุบัน) |
| :--- | :--- | :--- |
| **จำนวน API Call ต่อคลิป** | **1 Call เท่านั้น** (ส่งพร้อมกันทุกสไตล์) | **4 Parallel Calls** (แยก 1 สไตล์ต่อ 1 Call) |
| **โมเดลที่ใช้ประมวลผล** | MiniMax M3 (`minimax-m3`) | Qwen 72B (`qwen3p7-plus` หรือ `kimi-k2p7-code`) |
| **รูปแบบคำสั่ง (Prompt Shape)** | User Message + แนบเฟรมภาพ 24 เฟรม | System Prompt + User Message + แนบเฟรมภาพ 4 เฟรม |
| **การควบคุมผลลัพธ์** | สั่งให้ตอบเป็น JSON Object ตามสไตล์ที่กำหนด | สั่งให้ตอบเป็นข้อความธรรมดาครอบด้วยแท็ก `<caption_output>` |
| **ระดับความละเอียดคำสั่ง** | สั้น กระชับ เน้นใจความสำคัญ (2-3 ประโยคต่อสไตล์) | ละเอียดมาก มีกฎควบคุมคำเฉพาะ ตัวอย่าง (Exemplars) และข้อห้ามชัดเจน |

---

## 2. เจาะลึก Prompt ของ VeloCap (Single-Call JSON Multi-style)

นี่คือโครงสร้าง Prompt ที่ VeloCap ส่งไปยัง MiniMax M3 พร้อมรูปภาพ 24 เฟรมในหนึ่ง Call:

```text
[System/User Message]
You are an expert video captioner. You are shown a sequence of 24 frames sampled evenly across one video clip, in chronological order — treat them as a single continuous scene, not separate images.

Write ONE caption per requested style below. Every caption must:
- Accurately reflect what is actually visible across the frames (subjects, setting, actions, notable changes over time)
- Clearly sound like its assigned style — a reader should be able to tell the styles apart without seeing the labels
- Be 2-3 full sentences (roughly 25-45 words)
- Be genuinely distinct from the other styles — do not reuse the same sentence structure, jokes, or phrasing across styles

Styles to produce:
- "formal": Professional, objective, factual tone. Third-person, precise nouns, no jokes, no opinions. Describe setting, subjects, and actions the way a museum placard or news caption would.
- "sarcastic": Dry, ironic, lightly mocking wit — but still clearly describing what is actually happening in the video. The irony should come from *how* it's said, not from inventing unrelated content.
- "humorous_tech": Genuinely funny, weaving in specific technology, programming, or engineering references (e.g. threading, APIs, rendering, bugs) as the source of the joke — not just funny in general.
- "humorous_non_tech": Genuinely funny, everyday relatable humor with zero technical jargon — the kind of joke a non-technical friend would find funny.

Return a valid JSON object with EXACT keys: ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]. Return ONLY the JSON object, no preamble, no markdown fences.
```

### วิเคราะห์ผลลัพธ์ของสถาปัตยกรรมแบบ VeloCap:
1. **การบังคับความต่าง (Diversity Enforcement):** วลี *"Be genuinely distinct from the other styles — do not reuse the same sentence structure, jokes, or phrasing across styles"* บังคับให้โมเดลเปรียบเทียบคำตอบของตัวเองในแต่ละสไตล์ก่อนส่งผลลัพธ์ ช่วยลดปัญหาที่โมเดลใช้โครงสร้างประโยคซ้ำกัน (เช่น ขึ้นต้นด้วย "When you..." ทั้ง Tech และ Non-tech)
2. **ความสม่ำเสมอของข้อเท็จจริง (Factual Consistency):** เนื่องจากโมเดลประมวลผลข้อเท็จจริงทั้งหมดใน Session เดียว ข้อมูลพื้นฐานใน 4 สไตล์จึงตรงกัน 100% ต่างจากแบบแยก Call ที่บางโมเดลอาจเห็นภาพแล้วตีความวัตถุในฉากต่างกันเล็กน้อย ซึ่งทำให้ผู้ประเมินตัดคะแนนด้านความถูกต้อง (Accuracy)
3. **การคุมความยาว (Brevity Control):** การจำกัดคำบรรยายให้อยู่ในช่วง `25-45 words` ช่วยลดการเยิ่นเย้อของโมเดล ซึ่งช่วยประหยัดเวลาการประมวลผล (Response latency)

---

## 3. เจาะลึก Prompt ของ CaptionForge (Qwen Direct Mode)

ในฝั่ง CaptionForge จะแบ่งการทำงานเป็นแบบ **แยกสไตล์** โดยใช้โมเดล Qwen ซึ่งมีรูปแบบค่อนข้างเฉพาะเจาะจง:

```text
[System Prompt]
You turn a persona brief and a set of video frames into exactly one caption. Reply with plain English text only, and place the finished caption inside literal <caption_output> and </caption_output> tags. Never show your reasoning, never chat, never use markdown of any kind.

[User Message]
[คำบรรยาย Persona เฉพาะสไตล์ เช่น Humorous Tech]
One example of this register, from a DIFFERENT video — match its sharpness, never reuse its subject or joke: "[ตัวอย่างคำบรรยายล่วงหน้า]"

### RESPONSE FORMAT ###
1. Put one finished caption between <caption_output> and </caption_output> — the tags plus the caption are your entire reply.
2. Write in English about what the frames visibly show; never quote on-screen text and never name a real city, country, or landmark.
3. No emoji, no markdown, no notes or explanations before or after the tags.
```

### วิเคราะห์ผลลัพธ์ของสถาปัตยกรรมแบบ CaptionForge:
1. **เจาะลึกรายละเอียดของแต่ละสไตล์ได้ดีกว่า (Deeper Persona):** การมี Prompt ยาวและแยกเป็นสไตล์เดี่ยวทำความเข้าใจตัวละครได้ชัดเจนกว่า เช่น กฎการตัดคำต้องห้าม (bustling, vibrant) และระบบแยกประเภทคำศัพท์เทคนิค
2. **ความเร็วต่อ Call:** แม้ต้องส่ง 4 Call แต่สามารถทำเป็น Parallel ได้ แต่อย่างไรก็ตาม การส่งเฟรมภาพขนาดใหญ่จำนวนหลายภาพพร้อมกันส่งผลให้เกิด **API Latency** และเสี่ยงต่อ **Rate Limit 429** เป็นอย่างมาก
3. **ข้อจำกัดในการเชื่อมโยงสไตล์:** โมเดลไม่เห็นคำตอบของสไตล์อื่นๆ ในขณะตอบ ทำให้ไม่สามารถหลีกเลี่ยงความซ้ำซ้อนในด้านเนื้อหา (เช่น เล่นมุกในมุมเดียวกัน แต่ใช้ภาษาต่างกัน) ได้อย่างสมบูรณ์แบบ ต้องมารองรับความปลอดภัยผ่าน regex/similarity check ในภายหลัง

---

## 4. ข้อเสนอแนะและไอเดียสำหรับการพัฒนาบอร์ด Prompt ของคุณ

เพื่อการทำคะแนนที่สูงขึ้นเทียบเท่าหรือมากกว่า 0.91 เรามีทางเลือกหลัก 2 แนวทางในการปรับปรุงเรื่อง Prompt:

### แนวทางที่ 1: เปลี่ยนมาใช้ Single-Call (แนะนำสำหรับการเพิ่มความเร็วและป้องกัน Rate Limit)
* **การนำไปใช้:** ใช้โครงสร้าง Prompt ของ VeloCap ส่งไปยัง MiniMax M3 หรือ Qwen 72B ใน 1 Call เพื่อรับค่าเป็น JSON Object ที่มี 4 สไตล์
* **สิ่งที่จะดีขึ้น:** 
  * ป้องกันปัญหาการสร้างประโยคซ้ำ (เนื่องจากใช้ Context ร่วมกัน)
  * ประหยัดปริมาณ Token และค่าใช้จ่ายของ API
  * ป้องกันข้อผิดพลาดของแท็กหาย (Tag Miss) ใน Qwen Direct และป้องกัน Error 429
* **วิธีจัดการกับโมเดล:** กำหนด Schema ของ JSON ให้ชัดเจนผ่านทางระบบ API (เช่น ใช้ JSON Mode ของ Fireworks AI)

### แนวทางที่ 2: ปรับปรุง Prompt ของ Qwen Direct (หากต้องการรักษาระบบแยก Call ไว้)
* **แก้ไข Prompt ให้กระชับขึ้น:** ถอดข้อความยาวเหยียดที่โมเดลอาจจะไม่ได้นำไปใช้จริงออก (เช่น ข้อมูลจำกัดจำนวนคำและตัวอย่างบางส่วนที่ไม่ได้ช่วยเพิ่มคะแนนมากนัก)
* **เพิ่มคำสั่งควบคุมการเปิดประโยค:** บังคับใน Prompt เพิ่มเติมว่าห้ามขึ้นต้นประโยคด้วยโครงสร้างจำเจเพื่อเพิ่มคะแนนความต่างสไตล์

---
*หากคุณต้องการทดลองแปลงระบบไปเป็น Single-Call หรือปรับปรุง Prompt ในไฟล์ `src/prompts.py` แจ้งให้ทราบได้เลยครับ!*
