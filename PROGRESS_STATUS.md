# CaptionForge — สถานะโปรเจกต์ (อัปเดตล่าสุด 9 ก.ค. 2026)

Track 2: Video Captioning Agent — AMD Developer Hackathon: Act II
Deadline: **11 กรกฎาคม 2026**

## โปรเจกต์นี้คืออะไร / เป้าหมาย

Agent ที่ดูวิดีโอคลิปแล้วเขียนแคปชัน 4 สไตล์ (`formal`, `sarcastic`, `humorous_tech`,
`humorous_non_tech`) ต้องรันเป็น Docker container ที่อ่าน `/input/tasks.json` และเขียน
`/output/results.json` โดยไม่พังแม้จะเจอคลิปที่ไม่เคยเห็นมาก่อน (กรรมการทดสอบด้วยชุดคลิปลับ
~12 คลิป ที่มีเนื้อหาหลากหลายกว่า 3 คลิปตัวอย่างในโจทย์มาก) เป้าหมายรองคือชิงรางวัลพิเศษ
"Best Use of Gemma in Video Captioning" ($3,000 — มากกว่ารางวัลที่ 1 ของ Track 2 เอง)

## สถาปัตยกรรมหลัก

1. **Gemini 2.5 Flash** อ่านวิดีโอแบบ native (ภาพ+เสียงในตัว ไม่ต้องใช้ FFmpeg/Whisper แยก)
   ทำงานเป็น 2 stage: Stage 1 สร้าง "Scene Report" 10 หัวข้อ (มีหัวข้อ RISKS กันการเดามั่ว)
   → Stage 2 เอา Scene Report ไปเขียนแคปชัน 4 สไตล์แบบ JSON
2. **Gemma (ผ่าน Fireworks AI)** เป็น pass เสริมสำหรับสไตล์ตลก 3 อัน (polish + self-critique
   loop) เพื่อชิง bonus prize — ถ้าไม่มี key ระบบยัง fallback เป็น Gemini-only ได้ปกติ
3. **Runtime-budget-aware scheduling**: probe ขนาดไฟล์ก่อนแล้วเรียงคลิปหนักสุดไปก่อน,
   บังคับ deadline รวมทั้งโปรแกรมไม่เกิน 10 นาที, คลิปไหนไม่เสร็จทันใช้ fallback caption ทันที,
   `os._exit(0)` การันตีโปรแกรมจบตรงเวลาแม้มี thread ค้าง
4. **Credential baking**: Track 2 ไม่ inject key ให้ตอนรัน (ต่างจาก Track 1) จึงต้องฝัง
   `GEMINI_API_KEY`/`FIREWORKS_API_KEY` เข้า image ตอน `docker build --build-arg`

## เสร็จแล้ว ✅

- [x] เลือก Track 2 + วิเคราะห์ 3 track + bonus challenge แล้ว
- [x] Pipeline หลัก: Gemini 2.5 Flash (2-stage) + Gemma polish/critique ผ่าน Fireworks
- [x] Runtime-budget-aware scheduling — ทดสอบผ่านแล้ว (รวมถึงจำลอง clip ค้าง)
- [x] Credential baking เข้า Docker image (`--build-arg`) — แก้ bug ร้ายแรงที่จะทำให้ได้ 0 คะแนน
- [x] Retry logic สำหรับ Gemini error ชั่วคราว (503/429) — ปรับให้อ่านค่า `retryDelay`
      จาก API ตรงๆ แทนการเดาเวลาคงที่ (เจอจากการทดสอบจริงว่า fixed backoff สั้นเกินไป)
- [x] แก้ bug "Unknown mime type" — ไฟล์วิดีโอที่ไม่มีนามสกุล `.mp4` (เช่นจาก Google Drive)
      เคย upload เข้า Gemini ไม่ได้เลย ตอนนี้ระบุ `mime_type="video/mp4"` ตรงๆ แล้ว
- [x] Docker build/run ทดสอบผ่าน, push ขึ้น GHCR แบบ public แล้ว:
      `ghcr.io/kanokchat01/captionforge:latest`
- [x] Push โค้ดขึ้น GitHub public แล้ว: `https://github.com/Kanokchat01/captionforge`
- [x] Cover image สำหรับหน้า submit (1200x630) — เก็บที่ `submission_assets/captionforge_cover.png`
- [x] เว็บ demo แบบ local (`web_demo/`) — ใช้ทดสอบ/ดูผลแบบมี UI แทนแก้ JSON มือ ไม่ใช่ส่วนหนึ่ง
      ของ submission จริง (submission ยังเป็น headless Docker ตามเดิม)
- [x] ระบบสลับ Gemma provider ระหว่าง Fireworks (default, ใช้ตอน submit จริง) กับ OpenRouter
      (dev/test only, ประหยัด credit Fireworks ระหว่างทดสอบ) — ปลอดภัยเพราะ Dockerfile ไม่เคย
      bake ค่า `GEMMA_PROVIDER`/`OPENROUTER_API_KEY` เข้า image เลย
- [x] ทดสอบ stress test 8 คลิปพร้อมกัน (5 จากเพื่อน + 3 ทางการ) — เจอ 2 bug จริงและแก้แล้ว
- [x] ร่าง title/description/tags สำหรับฟอร์ม submit (`captionforge_submission_description.md`)

## เรื่องที่รอการตัดสินใจ (ยังไม่ได้ทำ รอ confirm ก่อน)

- **Gemini API เป็น free tier (5 requests/นาที)** — ตอนทดสอบ 8 คลิปพร้อมกันเจอ 429 quota
  เต็ม ถ้าคลิปลับจริง 12 คลิปก็มีความเสี่ยงเจอแบบเดียวกัน ทางเลือก:
  1. เปิด billing บัญชี Gemini API ใน Google AI Studio (ราคาถูก จ่ายตามการใช้จริง) — ตัดปัญหาขาดทุน
  2. ลด `CONCURRENCY` ใน `.env` (ตอนนี้ = 4 เหมือนเดิม ยังไม่ได้ลด)
  - ยังไม่ได้ลงมือทำอะไรทั้งสองทาง รอการตัดสินใจ

## ยังไม่เสร็จ

- [ ] **Fireworks API key จริง** — เช็คว่า credit "hackathon credits" ($50 ที่ผู้เข้าแข่งขัน
      ทุกคนได้ ไม่ต้องรอ approve) เข้าหรือยัง ตอนนี้ยังทดสอบผ่าน OpenRouter (dev only) อยู่
- [ ] **Video presentation** — ยังไม่ได้อัด
- [ ] **Slide deck** — ยังไม่ได้ทำ
- [ ] **กด Submit จริงบน lablab.ai** — ยังไม่ได้กด

## ไฟล์สำคัญ

- `src/main.py`, `src/gemini_client.py`, `src/gemma_polish.py`, `src/prompts.py`,
  `src/downloader.py`, `src/config.py` — โค้ด pipeline หลัก (ใช้จริงตอน submit)
- `web_demo/` — เว็บ demo local เท่านั้น ไม่เกี่ยวกับ submission
- `input/tasks.json` — **ต้องเป็น 3 คลิปทางการเท่านั้นก่อน commit/push** (มีสำรองไว้ที่
  `input/tasks_official_backup.json` เผื่อไปแก้เป็นชุดทดสอบแล้วลืมคืนค่า)
- `input/tasks_test8.json` — ชุดทดสอบ 8 คลิป (ไม่ใช่ของทางการ ไม่ต้อง push)
- `submission_assets/captionforge_cover.png` — cover image พร้อมใช้
- `Dockerfile` — bake `GEMINI_API_KEY`/`FIREWORKS_API_KEY` ตอน build เท่านั้น
- `README.md`, `STEP_BY_STEP_TH.md` — คู่มือ setup/build/push แบบละเอียด

## จุดที่ต้องระวังเวลากลับมาทำต่อ

- ผมมีสิทธิ์เข้าถึง `C:\captionforge` โดยตรง ไม่ต้อง copy ไฟล์เอง
- แก้โค้ดรอบไหน ต้อง build+push Docker ใหม่ และ push GitHub ใหม่ทุกครั้ง:
  ```
  docker buildx build --platform linux/amd64 --build-arg GEMINI_API_KEY=$env:GEMINI_API_KEY --build-arg FIREWORKS_API_KEY=$env:FIREWORKS_API_KEY -t ghcr.io/kanokchat01/captionforge:latest --push .
  git add . && git commit -m "..." && git push
  ```
- ก่อน push ทุกครั้ง เช็คว่า `input/tasks.json` เป็น 3 คลิปทางการ (ไม่ใช่ชุดทดสอบ) และ
  `.env` ไม่ได้ตั้ง `GEMMA_PROVIDER=openrouter` ค้างไว้ (ใช้ได้แค่ตอน dev เท่านั้น)
- ผมจะไม่ลงมือแก้อะไรเพิ่มเอง (เช่นปรับ `CONCURRENCY`, เปิด billing) จนกว่าจะได้รับคำสั่งชัดเจน
