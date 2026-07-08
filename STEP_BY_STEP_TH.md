# คู่มือลงมือทำทีละขั้น — CaptionForge (Track 2)

ทำตามลำดับนี้ตรงๆ ได้เลย แต่ละ phase มีวิธีเช็คว่า "ผ่านแล้ว" ก่อนไป phase ถัดไป

---

## Phase 0 — เตรียม API Key (ทำก่อนอย่างอื่นทั้งหมด)

### 0.1 Gemini API Key (บังคับ)
1. เข้า https://aistudio.google.com
2. ล็อกอินด้วย Google account
3. มุมซ้ายเลือก **Get API Key** → **Create API key**
4. copy key เก็บไว้ (จะเอาไปใส่ `.env`)

### 0.2 Fireworks API Key (ไม่บังคับ แต่ต้องมีถ้าอยากได้รางวัล Gemma bonus)
1. เช็คก่อนว่า credit จาก AMD AI Developer Program เข้าหรือยัง (ล็อกอิน fireworks.ai ด้วยบัญชีเดียวกับที่สมัคร ADP)
2. ถ้ามีแล้ว ไปหน้า **API Keys** ใน dashboard ของ fireworks.ai แล้ว copy key

**เช็คผ่าน:** มี string ของ Gemini key (ขึ้นต้นแบบ `AIza...`) พร้อมวางแล้ว

---

## Phase 1 — ตั้งเครื่องพัฒนา

เปิด VS Code แล้วเปิดโฟลเดอร์ `captionforge` (อยู่ในโฟลเดอร์ output ที่ผมสร้างให้) เปิด terminal ใน VS Code (`Ctrl+`` `) แล้วรันทีละบรรทัด:

```powershell
# 1. เช็คว่ามี Python
python --version

# 2. สร้าง virtual environment
python -m venv venv
.\venv\Scripts\activate

# 3. ติดตั้ง library ที่ต้องใช้
pip install -r requirements.txt

# 4. สร้างไฟล์ .env จาก template
copy .env.example .env
```

จากนั้นเปิดไฟล์ `.env` ที่เพิ่งสร้าง แล้ววาง key จริงลงไปแทนค่า placeholder:
```
GEMINI_API_KEY=<key จริงจาก Phase 0.1>
FIREWORKS_API_KEY=<key จริงจาก Phase 0.2 ถ้ามี>
```

**เช็คผ่าน:** รัน `pip list` แล้วเห็น `google-genai`, `requests`, `python-dotenv` อยู่ในลิสต์

---

## Phase 2 — รันทดสอบบนเครื่อง (ยังไม่ต้องใช้ Docker)

```powershell
python src/main.py
```

จะเห็น log ประมาณนี้: `[*] Reading tasks from input/tasks.json` ตามด้วยผลลัพธ์ทีละคลิป แล้วจบด้วย
`[+] Wrote 3 results to output/results.json in XX.Xs`

**สิ่งที่ต้องดูตอนนี้:**
- ตัวเลขวินาทีท้ายบรรทัดสุดท้าย (`in XX.Xs`) — เอาไปคูณ 4 (12 คลิปจริง หาร 3 คลิปที่ทดสอบ) เพื่อประเมินว่าจะพอในงบ 10 นาทีไหม ถ้าเกิน 150 วินาทีสำหรับ 3 คลิป ให้กลับไปดูหัวข้อ "ถ้าเวลาเกินงบ" ด้านล่าง
- เปิด `output/results.json` ดูว่าแคปชันทั้ง 4 สไตล์ออกมาสมเหตุสมผลไหม

**เช็คผ่าน:** โปรแกรมจบด้วย exit code 0 (ไม่ error) และ `output/results.json` มีครบ 3 task แต่ละ task มีครบ 4 คีย์สไตล์

**ถ้า error:** copy ข้อความ error เต็มๆ มาให้ผมดู จะช่วยแก้ให้

---

## Phase 3 — ตรวจคุณภาพ + ปรับจูน (ถ้าต้องการ)

เปิด `output/results.json` อ่านทีละแคปชัน:
- `formal` อ่านดูเป็นทางการจริงไหม
- `sarcastic` / `humorous_tech` / `humorous_non_tech` ตลกจริงไหม หรือดูเป็นมุกลอยๆ ทั่วไป

ถ้าไม่พอใจ ให้แก้ prompt ที่ `src/prompts.py` ฟังก์ชัน `build_caption_prompt()` แล้วรัน `python src/main.py` ใหม่ (ทำวนได้เรื่อยๆ จนกว่าจะพอใจ ยังไม่ต้อง build Docker ตอนนี้)

**ถ้าเวลาเกินงบ (จาก Phase 2):**
- ลด `MAX_CRITIQUE_RETRIES` ใน `.env` จาก 2 เป็น 1 หรือ 0
- เพิ่ม `CONCURRENCY` ใน `.env` จาก 4 เป็น 6-8 (ถ้าเน็ตไหว)
- หรือปิด self-critique/polish ชั่วคราว: ตั้ง `ENABLE_SELF_CRITIQUE=false` ใน `.env` เพื่อดูว่าตัว pipeline หลัก (ไม่มี Gemma) เร็วพอไหมก่อน

---

## Phase 4 — ติดตั้ง Docker Desktop (ถ้ายังไม่มี)

1. โหลดจาก https://www.docker.com/products/docker-desktop
2. ติดตั้งแล้ว restart เครื่องถ้าโปรแกรมขอ
3. เปิด Docker Desktop ทิ้งไว้ (ต้องเปิดค้างไว้ตอน build/run)
4. เช็คใน terminal: `docker --version` ต้องขึ้นเลขเวอร์ชัน ไม่ error

---

## Phase 5 — Build และรันทดสอบใน Docker

```powershell
# Build image
docker build -t captionforge .

# รันทดสอบ (mount input/output จริง + ส่ง env vars เข้าไป)
docker run --rm `
  -e GEMINI_API_KEY=$env:GEMINI_API_KEY `
  -e FIREWORKS_API_KEY=$env:FIREWORKS_API_KEY `
  -v ${PWD}/input:/input `
  -v ${PWD}/output:/output `
  captionforge
```

ถ้า PowerShell บ่นเรื่อง environment variable ไม่ขึ้น ให้ตั้งค่าก่อนรันด้วย:
```powershell
$env:GEMINI_API_KEY = "<key จริง>"
$env:FIREWORKS_API_KEY = "<key จริง>"
```

**เช็คผ่าน:** container รันจบเอง (ไม่ค้าง), `output/results.json` ถูกเขียนใหม่, เวลารวมอยู่ในงบที่ประเมินไว้จาก Phase 2

---

## Phase 6 — Push Docker image ขึ้น public registry

ใช้ GitHub Container Registry (ghcr.io) เพราะน่าจะมี GitHub account อยู่แล้ว:

```powershell
# 1. สร้าง Personal Access Token บน GitHub: Settings → Developer settings →
#    Personal access tokens → Tokens (classic) → เลือกสิทธิ์ write:packages

# 2. Login เข้า ghcr.io ด้วย token นั้น
docker login ghcr.io -u <ชื่อ GitHub username>
# ตอนถาม password ให้วาง token (ไม่ใช่รหัสผ่าน GitHub จริง)

# 3. Build แบบระบุ platform ให้ตรงกับ judging VM แล้ว push
# สำคัญมาก: Track 2 กรรมการรัน `docker run` เฉยๆ ไม่ส่ง -e ให้เราเลย
# (ต่างจาก Track 1) ต้องฝัง API key เข้าไปใน image ตอน build ด้วย --build-arg
docker buildx build --platform linux/amd64 `
  --build-arg GEMINI_API_KEY=$env:GEMINI_API_KEY `
  --build-arg FIREWORKS_API_KEY=$env:FIREWORKS_API_KEY `
  -t ghcr.io/<username>/captionforge:latest --push .
```

จากนั้นเข้า GitHub → โปรไฟล์ → **Packages** → เลือก package `captionforge` → **Package settings** → เปลี่ยน visibility เป็น **Public** (สำคัญมาก ไม่งั้นกรรมการ pull ไม่ได้ จะได้ 0 คะแนนทันที)

**เช็คให้ชัวร์ว่า key ฝังเข้า image จริง** ลองรันแบบไม่ใส่ `-e` เลยดู (จำลองแบบที่กรรมการจะรัน):
```powershell
docker run --rm -v ${PWD}/input:/input -v ${PWD}/output:/output ghcr.io/<username>/captionforge:latest
```
ถ้าไม่มี `-e` แล้วยังรันได้ผลลัพธ์ปกติ แปลว่า key ฝังเข้า image สำเร็จแล้ว

**เช็คผ่าน:** เปิด browser โหมด incognito (ไม่ล็อกอิน) แล้วเข้า `https://github.com/<username>?tab=packages` เห็น package นั้นได้โดยไม่ต้อง login

---

## Phase 7 — Push โค้ดขึ้น public GitHub repo

```powershell
git init
git add .
git commit -m "CaptionForge - Track 2 submission"
```

สร้าง repo ใหม่บน github.com (ตั้งเป็น **Public**, ไม่ต้อง initialize with README เพราะมีอยู่แล้ว) แล้ว:

```powershell
git remote add origin https://github.com/<username>/captionforge.git
git branch -M main
git push -u origin main
```

**สำคัญ:** เช็คว่า `.env` ที่มี key จริงอยู่ **ไม่ถูก push ขึ้นไปด้วย** (ต้องมี `.gitignore` ที่ exclude `.env` — ถ้ายังไม่มีให้สร้างไฟล์ `.gitignore` ใส่บรรทัด `.env` และ `venv/` ก่อน commit)

---

## Phase 8 — เตรียมของส่งบน lablab.ai

ต้องมีครบตามนี้ก่อนกด Submit:
1. Project Title + Short description + Long description (เขียนอธิบาย pipeline ตามที่คุยกันมา)
2. Cover image (รูปเดียว ใช้เป็นภาพหน้าปกโปรเจกต์)
3. Video presentation (อัดวิดีโอสั้นๆ เดโมว่าโค้ดทำงานยังไง ผลลัพธ์หน้าตาเป็นยังไง)
4. Slide presentation (สรุปปัญหา/วิธีแก้/สถาปัตยกรรม/เทคที่ใช้ AMD Dev Cloud, Gemini, Gemma, Fireworks)
5. Public GitHub repository URL (จาก Phase 7)
6. Docker image URL (จาก Phase 6) — ใส่ในช่องที่ lablab กำหนดสำหรับ Track 2

---

## Phase 9 — Submit

กลับไปหน้า event dashboard บน lablab.ai → กด **Submit project** → กรอกครบตาม Phase 8 → กด submit ก่อน deadline (11 กรกฎาคม)

แนะนำให้ submit เวอร์ชัน baseline ที่ผ่าน Phase 5-6 ให้ได้ก่อนอย่างน้อย 1 วันก่อน deadline แล้วค่อยอัปเดตซ้ำได้ถ้ามีเวลาเหลือ (ดีกว่าไม่มีอะไรส่งเลยเพราะรอปรับจนวินาทีสุดท้าย)
