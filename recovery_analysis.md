# Recovery Analysis — 13 ก.ค. 2026 (หลัง 0.77 บนบอร์ด)

> สถานะ ณ ~07:00 น. ไทย · deadline ขยาย ~7 ชม. (คาด ~12:40) · ระบบตรวจช้า ~3 ชม. 20 นาที/ครั้ง

## 1. เกิดอะไรขึ้นจริง ๆ กับ 0.77

- เมื่อคืนมีการกด submit ชนกันในทีม — **ตัวที่ถูกตรวจคือ build ของเพื่อน (คนละโค้ดกับ r6)** ได้ 0.77
- ⇒ **r6 ของเราไม่เคยถูกตรวจจริง** — คะแนนจริงล่าสุดของ pipeline เรายังคือ **r1 = 0.90**
- ⇒ สมมติฐาน "AMD ปรับจูน judge" อ่อนลงมาก: ทีมที่ถูกตรวจช่วงคืน 13 ก.ค. ได้คะแนนปกติ
  (SwiftCap 0.91 ตรวจ 05:25 · FourVoices 0.89 ตรวจ 02:23 · Divine 0.88 ตรวจ 23:56)
- **บทเรียนทีม: submission อ้าง docker tag `:latest`** — ใคร push ทับ `:latest` = เปลี่ยนตัวที่ถูกตรวจทันที
  **กติกาใหม่: ห้าม push `:latest` โดยไม่นัดกันก่อน; ทุก build ทดลองใช้ tag เฉพาะ (r1-restore, e2-minimax, ...)**

## 2. Diff: r1 (0.90 บอร์ด) vs r6 (ไม่เคยถูกตรวจ)

Engine เดียวกัน (`qwen_direct` บน `qwen3p7-plus`, 4 เฟรม @1024px, 4 call/คลิป ขนาน) ต่างกัน 3 ไฟล์:

| ไฟล์ | r6 เปลี่ยนอะไร | กระทบเนื้อหาแคปชัน? |
|---|---|---|
| `src/prompts.py` | เพิ่มประโยค `GROUNDING_DISCIPLINE` ใน sarcastic/humorous_tech/humorous_non_tech + เขียน persona `humorous_non_tech` ใหม่ | **ใช่ — ทุกคลิป** |
| `src/qwen_direct.py` | เพิ่ม `_INFLIGHT` semaphore (จำกัด 3 concurrent), attempts 3→4, length guard 60 คำ | timing/ขอบเคส |
| `src/fireworks_vision_client.py` | backoff [3,6] → [2,5,10,18] | timing |

- ซอร์ส r1 ของแท้อยู่ครบใน `_r1_src/` · แคปชัน r1 จริง + eval อยู่ใน `output/results_v6_r1(.eval).json`
- Local eval (gemini-2.5-flash) ให้ทั้ง r1 และ r6 ≈ 0.92 — แยกสองตัวนี้ไม่ออก แต่ r1 มีบอร์ดยืนยัน 0.90 ⇒ **default = r1**
- snapshot r6 commit ไว้แล้ว: `307c340`

## 3. Intel คู่แข่ง: สูตร minimax-m3 single-call (พิสูจน์บนบอร์ดโดย 2 ทีม)

### SwiftCap 0.91 (ตรวจใต้ judge ปัจจุบัน 05:25 วันนี้) — repo: github.com/BatoolZyidi/SwiftCap
- `accounts/fireworks/models/minimax-m3` — **1 call/คลิป ออกครบ 4 สไตล์เป็น JSON** (temp 0.7, max_tokens 3000)
- เฟรม 1fps ตามความยาวคลิป, resize ≤512px, JPEG q70, stream ผ่าน OpenCV (ไม่ดาวน์โหลดไฟล์) + กรองเฟรมเขียว/เสีย
- **แคปชันสั้น 12–35 คำ / 1–2 ประโยค** · accuracy-first · แบนมโนทุกชนิด (ชื่อ/แบรนด์/สถานที่/อารมณ์/เสียง/ข้อความบนจอ)
- JSON validation เข้ม + retry 1 ครั้งพร้อมคำสั่งเข้มขึ้น · แยก process ต่อคลิป · wall-clock guard <10 นาที

### VeloCap 0.91 (judge เดิม) — สูตรเดียวกัน ต่างรายละเอียด
- 24 เฟรม @640×360 JPEG q78 · single JSON call · word-overlap guard (คู่สไตล์ซ้ำ >0.75 = reject, <8 คำ = reject) · timeout 45s + jitter backoff

### ข้อควรระวัง
- Benchmark ของเราเอง (11 ก.ค.) เคยให้ minimax เป็น **text-only writer แค่ 0.666 + JSON พัง 2/3** — แต่โหมด multimodal single-call มีบอร์ดยืนยันจาก 2 ทีม → ต้องมี JSON parsing + rescue chain ที่แข็งแรง
- แคปชัน r1 เรายาวมาก (humorous_tech เฉลี่ย 71.3 คำ, max 107) — ถ้า judge ไม่ reward ความยาว ตัวสั้นแบบ SwiftCap ได้เปรียบ

## 4. แผน

1. **Track A — r1-restore (candidate หลัก):** restore 3 ไฟล์จาก `_r1_src/` → smoke 3 คลิป → `docker build -t captionforge:r1-restore .` → zero-flag run <600s → **พร้อมส่ง รอเคลียร์กับเพื่อนก่อน push**
2. **Track B/E1 — สลับโมเดลเฉย ๆ:** pipeline r1 + `QWEN_DIRECT_MODEL=minimax-m3` (ไม่แก้โค้ด) → eval 15 คลิป ×2 — ตอบคำถาม "kimi/qwen → minimax โอเคไหม"
3. **Track B/E2 — engine ใหม่ `minimax_single`:** ตามสูตร SwiftCap (1 call JSON 4 สไตล์, เฟรม adaptive 8–24 @640px, 12–35 คำ, validate + retry + rescue) → eval ×2 → ต้อง **ชนะ r1 ใน local judge** ถึงจะพิจารณาส่ง
4. **การส่ง (ผู้ใช้กดเอง):** ส่ง r1-restore เร็วสุดหลังเคลียร์ทีม → E2 เป็น upside shot เฉพาะถ้าผ่าน gate สวยและเวลาตรวจทัน · ห้ามส่งตัวที่ gate ไม่ผ่าน · ห้ามส่งใน 30 นาทีสุดท้ายโดยไม่มี docker smoke

## 5. คำสั่งส่งงาน (เติมให้ครบตอน build เสร็จ)

```powershell
# หลังเคลียร์กับเพื่อนแล้วเท่านั้น:
# docker tag captionforge:r1-restore <registry>/<repo>:latest
# docker push <registry>/<repo>:latest
# แล้วไปกด resubmit บน lablab
```
