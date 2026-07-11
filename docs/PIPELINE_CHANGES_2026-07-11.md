# CaptionForge — สรุปการปรับปรุง Pipeline (2026-07-11)

รายงานนี้สรุป (1) สถานะโปรเจคปัจจุบัน (2) pipeline ใหม่หลังแก้ (3) รายการสิ่งที่แก้ทุกไฟล์
(4) การประเมินว่ารับ 12 คลิปในงบ 10 นาทีได้จริงไหม และ (5) ความเสี่ยงที่เหลือ

---

## 1. สถานะโปรเจค

- **ก่อนแก้:** `output/results.json` เป็นข้อความ fallback timeout ครบทั้ง 12 คลิป → คะแนน 0
  ทั้งกระดาน เพราะ pipeline ชี้ไปโมเดล `minimax-m3` ที่ตอบ JSON พังบ่อย + งบเวลาถูก
  download คลิป UHD กินหมด
- **หลังแก้:** pipeline รันได้จริง exit 0, JSON ถูกต้อง, ทดสอบ 3 คลิป (แคช) end-to-end
  ได้ caption คุณภาพดีครบ 4 สไตล์ใน 81 วินาที คะแนน self-critique 9–10/10
- **เป้าหมาย:** leaderboard Track 2 อันดับ 1 = 0.91, ต้องการ > 0.90

---

## 2. Pipeline ปัจจุบัน (4 ขั้น)

```
tasks.json
   │
   ├─ [probe] HEAD ทุกคลิป → จัดคิวหนักก่อน (heaviest-first)
   │
   ▼  (ThreadPoolExecutor, CONCURRENCY=6)
┌──────────────────────────────────────────────────────────────┐
│ ต่อ 1 คลิป:                                                    │
│                                                                │
│ 1. DOWNLOAD  (retry×3, .tmp→rename, wall-cap 150s)             │
│                                                                │
│ 2. STAGE 1 — SCENE REPORT   [vision: kimi-k2p6]                │
│    • adaptive frames: 1 เฟรม/~8s, clamp 8–16 เฟรม, ย่อ 768px  │
│    • ได้รายงานฉาก 10 หัวข้อ (มี RISKS กัน hallucination)       │
│    • degrade chain: ลดเหลือ 4 เฟรม → สลับ qwen3p7-plus         │
│                                                                │
│ 3. STAGE 2 — BEST-OF-N      [text: glm-5p2]                    │
│    • เจน 3 ชุด caption ขนานกัน (temp 0.6 / 0.85 / 1.0)         │
│                                                                │
│ 4. JUDGE PASS              [judge: qwen3p7-plus]               │
│    • pick-best: เลือก caption ดีสุด "ต่อสไตล์" จาก 3 ชุด        │
│    • self-critique: ถ้าคะแนน < 8/10 → rewrite ด้วย feedback    │
│      (สูงสุด 2 รอบ, ข้ามอัตโนมัติเมื่อเวลาใกล้หมด)              │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
results.json  (การันตี: ทุก task_id มีแถว, ทุก style ไม่ว่าง, valid JSON)
```

### บทบาทโมเดล (เลือกจาก benchmark 2026-07-11)

| บทบาท | โมเดล | เหตุผล |
|---|---|---|
| Stage 1 vision | `kimi-k2p6` | scene report ละเอียด+ขุดมุกเก่งสุด, ไม่ hallucinate เทียบภาพจริง |
| Stage 1 fallback | `qwen3p7-plus` | vision-capable, ใช้เมื่อ kimi ล้มบนคลิปนั้น |
| Stage 2 caption | `glm-5p2` | **ชนะ benchmark: 0.874** (qwen 0.850, kimi-k2p7-code 0.830, minimax-m3 0.666) |
| Judge/pick/polish | `qwen3p7-plus` | รองแชมป์+เร็วสุด, คนละตระกูลกับ writer (กัน self-bias) |

> **ข้อค้นพบ:** `GET /v1/models` ของ Fireworks แสดงรายชื่อไม่ครบ — ต้องทดสอบด้วย chat
> call จริงเท่านั้น. `minimax-m3` ถูกถอดเพราะตอบ JSON พัง 2/3 คลิปทั้งที่เปิด json_mode

---

## 3. รายการสิ่งที่แก้ (ต่อไฟล์)

### `src/config.py`
- เปลี่ยน default โมเดล: vision `minimax-m3` → **`kimi-k2p6`**; text → **`glm-5p2`**;
  เพิ่ม `FIREWORKS_VISION_FALLBACK_MODEL`, `FIREWORKS_JUDGE_MODEL` (= qwen3p7-plus)
- คืน `ENABLE_SELF_CRITIQUE`/`ENABLE_MINIMAX_POLISH` ให้อ่านจาก env (เดิม hardcode `False` ทับ)
- เพิ่ม adaptive frames: `MIN_FRAMES_PER_CLIP=8`, `MAX_FRAMES_PER_CLIP=16`, `SECONDS_PER_FRAME=8`
- เพิ่ม `BEST_OF_N=3`; `CONCURRENCY` 4 → **6**
- ใส่คอมเมนต์อ้างอิงผล benchmark ทั้งหมด

### `src/fireworks_vision_client.py`
- เขียน `caption_clip()` ใหม่: คืน **list ของ candidate caption sets** (เดิมคืน dict เดียว)
- แยกเป็น `_scene_report()` + `_generate_candidates()` (Best-of-N ขนานกันด้วย ThreadPoolExecutor)
- **adaptive frame sampling** ตามความยาวคลิป
- **degrade chain** ใน Stage 1 (ลดเฟรม → สลับโมเดลสำรอง)
- เพิ่ม `reasoning_effort: "none"` ทุก call (กัน kimi leak ความคิดลง content + เร็วขึ้นเท่าตัว)
- `_extract_json()` ทนทานขึ้น: รับ JSON ที่มีขยะต่อท้าย (raw_decode) — เคสที่ minimax-m3 พัง

### `src/minimax_polish.py`
- เพิ่มเมธอด **`pick_best()`** (ให้ judge เลือก candidate ดีสุดต่อสไตล์)
- ชี้โมเดลไปที่ `FIREWORKS_JUDGE_MODEL` (qwen3p7-plus)
- `_extract_json()` ทนทานแบบเดียวกับ vision client

### `src/prompts.py`
- เพิ่ม `PICK_BEST_SYSTEM_PROMPT` + `build_pick_best_prompt()`
- **OCR guard**: ห้าม quote ข้อความบนป้าย/จอถ้าอ่านไม่ชัด (จับได้จาก test ที่อ่านป้าย
  "ILLIES" เป็น "ELITE")
- judge/polish prompt ได้รับ **กฎ per-style เต็ม** (word count/emoji) ไม่ใช่แค่คำอธิบายสั้น

### `src/main.py`
- ต่อ Best-of-N เข้า flow: วน `styles` → `pick_best()` → critique loop
- **guard style ว่าง**: ถ้า caption ว่าง เติม fallback (กัน style หายทำคะแนนคลิปเป็น 0)
- อัปเดต docstring ให้ตรงโมเดลจริง

### `src/downloader.py`
- **เพิ่ม wall-clock cap ต่อการโหลด** (`MAX_DOWNLOAD_WALL_SECONDS=150`) — timeout เดิม
  จับได้แค่การค้าง จับ "โหลดช้าเรื่อยๆ กินงบทั้งรัน" ไม่ได้ (ต้นเหตุที่ทำ 12-คลิปตายเดิม)
- แยก connect/read timeout เป็น tuple `(10, 30)`
- ไม่ retry เมื่อชน wall-cap (ลิงก์แค่ช้า ไม่ใช่ flaky — retry เปลืองงบเปล่า)

### `web_demo/app.py`
- อัปเดตให้เข้ากับ `caption_clip()` แบบใหม่ (candidates list + pick_best)

### `README.md`, `.env`, `.env.example`, `Dockerfile`
- แก้ให้ตรงโมเดล/สถาปัตยกรรมจริง (เดิมยังพูดถึง Gemini/Gemma ที่ลบไปแล้ว)
- ลบ `GEMINI_API_KEY` ออกจาก Dockerfile (ไม่ใช้แล้ว) — bake เฉพาะ `FIREWORKS_API_KEY`

---

## 4. รับ 12 คลิปในงบ 10 นาทีได้ไหม?

### การันตีแบบแข็ง (hard guarantee) — ได้แน่นอน
กลไกงบเวลา**บังคับ**ให้จบภายใน 10 นาทีเสมอ ไม่ว่าอะไรจะเกิด:
- `futures_wait(timeout = deadline − 30s)` — ไม่รอเกิน deadline
- คลิปไหนไม่ทัน → เขียน fallback caption ทันที ไม่ลากคลิปอื่น
- `os._exit(0)` — บังคับปิด ไม่ค้างรอ thread ที่ hang
- ทุก task_id ได้แถว, ทุก style ไม่ว่าง, JSON ถูกต้องเสมอ

→ **exit 0 + valid JSON ครบ 12 คลิป การันตี 100%** (ต่อให้เน็ต/API มีปัญหา อย่างน้อยได้ fallback)

### คุณภาพเต็ม (ทุกคลิปได้ caption จริง) — ได้ ถ้าเน็ตกรรมการเร็ว (คาดว่าเร็ว)
เวลาที่วัดจริง:
- 1 คลิป (API อย่างเดียว, ไม่ติดเน็ต): vision ~37–45s + Best-of-N ~5–14s + judge หลาย call ≈ **45–81s/คลิป**
- 3 คลิปแคช ขนานกัน (CONCURRENCY=6): **จบใน 81s**

ประมาณการ 12 คลิปบน VM กรรมการ (เน็ต datacenter, download ไม่กี่วินาที):
- CONCURRENCY=6 → 12 คลิป = 2 ระลอก × ~81s ≈ **160–250 วินาที**
- งบ 540s → **เหลือ margin ~2 เท่า** ✅

### ข้อควรระวัง (ยังไม่ได้พิสูจน์บนเน็ตเร็วจริง)
ที่เครื่อง dev **เน็ตช้ามาก** (วัดได้ 3.4–14 KB/s) จึงยังไม่เคยรัน 12 คลิปครบบนเน็ตเร็ว
ตัวเลข 160–250s เป็นการประมาณจาก API latency ล้วน **ควรรัน 12 คลิปครบ 1 ครั้งบนเน็ตเร็ว
(หรือบน AMD Developer Cloud) ก่อน submit จริง** เพื่อยืนยัน

---

## 5. ความเสี่ยงที่เหลือ (Risk Register)

| ระดับ | ความเสี่ยง | สถานะ / การรับมือ |
|---|---|---|
| 🔴 | API key ฝังใน public image → ถูก pull ไปแกะ, เครดิต $50 อาจถูกดูด | ใช้คีย์ disposable, เฝ้าดูเครดิต, revoke หลังงาน |
| 🔴 | โมเดลถูกถอด/เปลี่ยนพฤติกรรมกลางงาน (เพิ่งเกิดกับ minimax-m3) | มี fallback chain; **ควร smoke-test ก่อน submit ทุกครั้ง** |
| 🟡 | Fireworks API ช้า/rate-limit ตอน 6 คลิปยิงพร้อมกัน | critique loop มี time-guard ข้ามได้, base caption ยังถูกเขียน |
| 🟡 | vision call ~40s > กติกากลาง "30s/request" | ตีความว่า 10-min รวมคือตัวคุม Track 2 (สมมติฐาน, ไม่ชัด 100%) |
| 🟡 | ยังไม่ได้ทดสอบ 12 คลิปบนเน็ตเร็ว | ต้องทดสอบ 1 ครั้งก่อน submit |
| 🟢 | เน็ต dev ช้า (3.4–14 KB/s) | ไม่ใช่ปัญหา production — VM กรรมการเน็ตแรง |
| 🟢 | JSON พัง / style หาย = 0 | guard หลายชั้น (robust parser, ห้าม style ว่าง, ครบทุก task_id) |

---

## 6. ขั้นตอนก่อน submit (ทีมทำเอง)

1. เปิด Docker Desktop → `docker buildx build --platform linux/amd64
   --build-arg FIREWORKS_API_KEY=$KEY -t ghcr.io/<you>/captionforge:latest --push .`
2. ทดสอบ `docker run` แบบ **ไม่มี -e flags** (จำลองกรรมการ)
3. รัน 12 คลิปครบ 1 ครั้งบนเน็ตเร็ว ดูว่าจบใน budget + ได้ caption จริงครบ
4. Submit (จำกัด 10 ครั้ง/ชม.) → ดูคะแนน leaderboard
