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

## 5. ผลการทดลอง (13 ก.ค. เช้า — local vision judge gemini-2.5-flash, 15 คลิป, รัน eval 2 รอบ)

| candidate | โมเดล / รูปแบบ | local score | health | สถานะ |
|---|---|---|---|---|
| **r1** (`captionforge:v6-r1`) | qwen3p7-plus, 4 call/คลิป, prompt r1 | 0.9142 (+**0.90 บนบอร์ดจริง**) | image เดิมของแท้, zero-flag ผ่าน 64s | ✅ **candidate หลัก** |
| **E1** (`captionforge:e1-minimax-swap`) | minimax-m3, 4 call/คลิป, prompt r1 เป๊ะ | **0.9179** (สูงสุด) | tag ครบ 60/60, 0 fallback, เร็วกว่า 3 เท่า (46s/15คลิป) | ✅ ผ่าน gate — upside shot |
| **E2** (`captionforge:e2-minimax`) | minimax-m3, 1 call JSON 4 สไตล์, 12–35 คำ | 0.8992 | 0 fallback, retry 4, rescue 0 | ❌ **ไม่ผ่าน gate (ต้อง ≥0.92) — ห้ามส่ง** |
| r1-restore (`captionforge:r1-restore`) | build ใหม่จากซอร์ส r1 ที่ restore | = r1 | zero-flag ผ่าน 48.5s | ✅ สำรองของ v6-r1 |

ข้อสังเกต: E2 เสีย accuracy ในสไตล์ฮา (0.80–0.86) เพราะแคปชันสั้นใส่ข้อเท็จจริงได้น้อยลง — local judge ให้รางวัลรายละเอียด (สอดคล้องผลทดลอง R2-4f เดิม) แต่ judge บอร์ดอาจไม่เหมือนกัน ทั้งนี้ตามเกณฑ์ที่ตกลงกัน E2 ไม่ผ่าน gate จึงไม่ส่ง

## 6. คำสั่งส่งงาน (ผู้ใช้กดเองหลังเคลียร์กับเพื่อนแล้วเท่านั้น)

⚠️ ก่อนส่ง: เช็คว่า submission บน lablab ชี้ที่ `ghcr.io/blackkidx/captionforge:latest` (ไม่ใช่ `kanokchat01`) — ถ้ายังชี้ผิด ต้อง resubmit ด้วย URL ของเรา

```powershell
# ── ตัวเลือกแนะนำ: r1 ตัวจริงที่เคยได้ 0.90 (image เดิม ไม่ผ่านการ build ใหม่) ──
docker tag captionforge:v6-r1 ghcr.io/blackkidx/captionforge:latest
docker push ghcr.io/blackkidx/captionforge:latest
# แล้วไปกด resubmit บน lablab ให้ชี้ image นี้

# ── ตัวเลือก upside (ผ่าน gate, local สูงสุด 0.9179 แต่ยังไม่เคยขึ้นบอร์ด): E1 ──
# docker tag captionforge:e1-minimax-swap ghcr.io/blackkidx/captionforge:latest
# docker push ghcr.io/blackkidx/captionforge:latest
```

Timeline ที่ต้องรู้: ระบบตรวจใช้เวลา ~3 ชม. 20 นาที — ถ้าต้องการให้คะแนนกลับก่อน deadline (~12:40) ต้องส่งภายใน ~09:15

## 7. บันทึกเหตุการณ์ต่อเนื่อง

**พบว่า `:latest` เพี้ยนอีกรอบ:** เช็ค GHCR package page พบว่า `ghcr.io/blackkidx/captionforge:latest` ชี้ไปที่ digest `sha256:0ce2e0218c4b...` ซึ่งตรงกับ `v6-r6` (ไม่ใช่ r1) — เป็นเศษตกค้างจากเหตุการณ์ submit ชนกันคืนก่อนหน้า (พร้อมกับที่ kanokchat01 โดนตรวจเป็น 0.77) ไม่มีใครตั้งใจ push ตัวนี้

**ตรวจสอบ r1 ก่อนแก้ (ผ่านทุกชั้น):**
- Source: `qwen_direct.py` + `fireworks_vision_client.py` SHA256 ตรงกับ `_r1_src/` เป๊ะ; `prompts.py` เนื้อหา r1 เป็น prefix ที่ไม่ถูกแตะ; `config.py`/`main.py` diff เป็นการเพิ่มเท่านั้น ไม่แตะ path `qwen_direct`
- Image: `docker inspect captionforge:v6-r1` digest `sha256:056814bcc5f2...` ตรงกับ `ghcr.io/blackkidx/captionforge:v6-r1` ที่เคย push ไปแล้วเป๊ะ (สร้าง 12 ก.ค. 08:49 UTC ก่อนเหตุการณ์ทั้งหมด)
- Fresh eval (generate ใหม่ 15 คลิป ไม่ใช่ eval ซ้ำของเก่า): **0.9192** (≥ baseline 0.9142) — โค้ดที่ restore มาทำงานถูกต้อง

**แก้ไขแล้ว:** `docker tag captionforge:v6-r1 ghcr.io/blackkidx/captionforge:latest` → `docker push` สำเร็จ, digest ปลายทาง `sha256:056814bcc5f291b5...` ตรงกับ v6-r1 ยืนยันแล้ว — **`:latest` กลับมาเป็น r1 (0.90) เรียบร้อย**

รอผลตรวจรอบใหม่ (~3 ชม. 20 นาทีจากนี้) + ติดตาม ticket ที่แจ้งผู้จัดไว้เรื่องความล่าช้า

---

## 8. 0.69 บนบอร์ด (13 ก.ค. 14:12) — ไม่ใช่คะแนนของ r1

**ไทม์ไลน์พิสูจน์:** บอร์ด scored 14:12 · ระบบตรวจใช้ ~3 ชม. 20 นาที ⇒ pull image ตอน ~10:50 · แต่เราเพิ่ง retag `:latest` → r1 ตอน **11:18** (commit 62516e8) ⇒ **ตัวที่โดนตรวจได้ 0.69 คือ r6 ที่ค้างอยู่** ส่วน r1 ที่ resubmit 15:00 ยังตรวจไม่เสร็จ (คาด ~18:20)

**ลายเซ็นของเลข 0.69:** generic fallback ได้ style ~0.5 แต่ accuracy ~0 ⇒ ~0.25/คลิป
แก้ `0.91 − (k/12) × 0.66 = 0.69` ⇒ **k ≈ 4 คลิปตกไป fallback** — ตรงกับที่ r6 ใส่ `_INFLIGHT` semaphore จำกัด in-flight call ไว้ 3 ทั้งที่ pipeline ต้องการ 16 (CONCURRENCY=4 × 4 สไตล์) บนเครื่องตรวจที่ช้ากว่า ⇒ ไล่ไม่ทัน ชน time cutoff ⇒ generic fallback
**ไม่ใช่ปัญหา prompt** — prompt r1 คือตัวที่ทำ 0.90

## 9. v7-hard — candidate สำรอง (`ghcr.io/blackkidx/captionforge:v7-hard`)

หลักการ: **happy path เหมือน r1 ทุกอย่าง** (prompt/model/4 เฟรม@1024/temp 0.7/backoff [3,6] เดิมเป๊ะ) แก้เฉพาะ failure path ทุกตัวมี env flag `HARDEN_*` ปิดได้โดยไม่ต้อง build ใหม่

| | สิ่งที่แก้ |
|---|---|
| H1 | retry มี jitter + รู้เวลาเหลือ (ไม่ sleep เข้าไปใน retry ที่ยังไงก็ไม่ทัน) |
| H2 | stagger เวลาเริ่มของแต่ละคลิป — **ไม่ใช่ semaphore** (semaphore คือตัวที่ฆ่า r6) |
| H3 | ขั้นบันไดกู้ก่อนถึง generic fallback: emergency 1 เฟรม → re-voice ข้อเท็จจริงจากสไตล์ที่สำเร็จ |
| H4 | `[health] fallback_clips=N` telemetry |
| H5 | ดึงเฟรมตรงจาก URL เมื่อ download ตาย (เดิม: download ตาย = เสียทั้งคลิป 4 สไตล์) |

**ผลวัด (15 คลิป, vision judge gemini-2.5-flash):**

| สถานการณ์ | r1 | v7-hard |
|---|---|---|
| ปกติ | 0.9142 | **0.9108 / 0.9113** (เท่ากันในกรอบ noise, 0 fallback) |
| ถูก throttle 75% | 0.8600 (6 คลิปตก) | **0.9133** (1 คลิปตก) |
| download ตายหมด | เสีย 15/15 คลิป | เสีย 7/15 (กู้ได้ 8 คลิป) |
| zero-flag docker | — | 281s/600s, 15×4 ครบ, fallback_clips=0 |

⇒ **v7-hard ไม่เคยแย่กว่า r1 และดีกว่ามากตอนเจอปัญหา**

## 10. กติกาตัดสินใจตอนผล r1 ออก (~18:20)

ผู้จัดตรวจ **image ตัวสุดท้ายที่ `:latest` ชี้อยู่ หลัง deadline** ⇒ `:latest` ณ ตอน cutoff = คะแนนจริง

- **r1 ≥ 0.88** → เครื่องตรวจปกติ, 0.69 คืออุบัติเหตุ image ล้วน ๆ → **คง `:latest` = r1 ไม่ต้องทำอะไร** (สาขาที่คาด)
- **r1 ออกมา ~0.69–0.80** → ยืนยันว่าเครื่องตรวจ starve เรา คลิปตก fallback → **สลับ `:latest` → v7-hard** (ตัวเดียวที่แก้อาการนี้ตรงจุด)
- **r1 ไม่ทันตรวจ** → คง `:latest` = r1 (มีบอร์ดยืนยัน) ห้ามเสี่ยงกับตัวที่ไม่เคยขึ้นบอร์ด

คำสั่งสลับ (กดเองเมื่อตัดสินใจแล้วเท่านั้น + เคลียร์กับทีมก่อน):
```powershell
docker tag captionforge:v7-hard ghcr.io/blackkidx/captionforge:latest
docker push ghcr.io/blackkidx/captionforge:latest
```
ย้อนกลับเป็น r1: `docker tag ghcr.io/blackkidx/captionforge:v6-r1 ghcr.io/blackkidx/captionforge:latest; docker push ...`

digest ปัจจุบัน: `:latest` = `:v6-r1` = `sha256:d2f1cba8a0b5...` · `:v7-hard` = `sha256:e78d3c3091c2...`
