# CaptionForge — สถานะงาน (อัปเดตล่าสุด)

Deadline: **11 กรกฎาคม 2026**

## เสร็จแล้ว ✅

- [x] เลือก Track 2 (Video Captioning) + วิเคราะห์ 3 track แล้ว
- [x] โค้ด pipeline: Gemini 2.5 Flash (2-stage: scene report -> 4 captions) + Gemma polish/critique ผ่าน Fireworks
- [x] Runtime-budget-aware scheduling (deadline enforcement, heaviest-first, fallback ทุกจุด) — ทดสอบผ่านแล้ว
- [x] ทดสอบรัน local (`python src/main.py`) — ผ่าน คุณภาพแคปชันดี
- [x] ทดสอบรันใน Docker (`docker run`) — ผ่าน
- [x] Push Docker image ขึ้น GHCR แบบ public: `ghcr.io/kanokchat01/captionforge:latest`
- [x] Push โค้ดขึ้น GitHub แบบ public: `https://github.com/kanokchat01/captionforge`
- [x] ร่าง title/description/tags สำหรับฟอร์ม submit แล้ว (ไฟล์ `captionforge_submission_description.md`)

## ยังไม่เสร็จ — ทำต่อพรุ่งนี้

- [ ] **Fireworks API key** — เช็คว่าอนุมัติมาหรือยัง ถ้ามาแล้วใส่ใน `.env` แล้วรันทดสอบใหม่เพื่อดูผล Gemma polish จริง (ตอนนี้ยังรันแบบ Gemini-only)
- [ ] **Cover image** — ยังไม่มี
- [ ] **Video presentation** — ยังไม่ได้อัด
- [ ] **Slide deck** — ยังไม่ได้ทำ
- [ ] **กด Submit จริงบน lablab.ai** — ยังไม่ได้กด (แนะนำให้ลอง submit แบบร่างเร็วๆ นี้ด้วย repo+image ที่มีอยู่แล้ว เผื่อเช็คว่าระบบกรรมการ pull ได้จริง)

## จุดที่ต้องระวังเวลากลับมาทำต่อ

- ผมมีสิทธิ์เข้าถึง `C:\captionforge` โดยตรงแล้ว ไม่ต้อง copy ไฟล์เองอีก
- ถ้าจะแก้โค้ดรอบหน้า ต้อง build+push Docker ใหม่ และ push GitHub ใหม่ทุกครั้งที่แก้ (`docker buildx build --platform linux/amd64 -t ghcr.io/kanokchat01/captionforge:latest --push .` แล้ว `git add . && git commit -m "..." && git push`)
