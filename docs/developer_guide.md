# 💻 คู่มือสำหรับ Developer: การขึ้นโครงโปรเจกต์และเชื่อมต่อ API (Track 2)
> **ชื่อไฟล์:** `developer_guide.md`
> **เป้าหมายวันนี้:** สร้างสคริปต์ Python ที่ดาวน์โหลดวิดีโอ -> ส่งไปวิเคราะห์ที่ Gemini API -> คายผลลัพธ์ลง JSON ได้ถูกต้องตามเกณฑ์

---

## 📂 1. โครงสร้างโฟลเดอร์โปรเจกต์ (Project Structure)
ให้สร้างโฟลเดอร์และไฟล์ตามโครงสร้างนี้ในเครื่องเครื่องตัวเอง:

```
hackathon-video-captioner/
├── input/
│   └── tasks.json             # ไฟล์จำลองโจทย์ที่สร้างขึ้นมาเทส
├── output/
│   └── (results.json)         # ไฟล์คำตอบที่สคริปต์เราจะเขียนขึ้นมา (ห้ามสร้างเอง)
├── src/
│   ├── __init__.py
│   ├── main.py                # Entry Point หลักของโปรเจกต์
│   ├── config.py              # จัดการ API Keys และ Env ต่างๆ
│   ├── downloader.py          # ฟังก์ชันดาวน์โหลดคลิปวิดีโอจาก URL
│   ├── pipeline.py            # ส่วนเชื่อมต่อ Gemini API และประมวลผล
│   └── app_dev_ui.py          # (Optional) หน้าเว็บ Streamlit สำหรับเทสกันเอง
├── .env                       # เก็บ API Key สำหรับ Local Dev (ห้ามเอาลง Docker)
├── requirements.txt           # รายการแพ็กเกจ
└── Dockerfile                 # สเปคของตู้คอนเทนเนอร์ส่งงาน
```

---

## 🛠️ 2. การเตรียมสภาพแวดล้อม (Local Setup)

1. **สร้าง Virtual Environment:**
   ```bash
   python -m venv venv
   # สำหรับ Windows:
   .\venv\Scripts\activate
   # สำหรับ macOS/Linux:
   source venv/bin/activate
   ```

2. **สร้างไฟล์ `requirements.txt`:**
   ```
   google-genai==0.1.1
   requests==2.31.0
   pydantic==2.6.4
   python-dotenv==1.0.1
   ```
   *หมายเหตุ: ติดตั้งด้วยคำสั่ง `pip install -r requirements.txt`*

3. **สร้างไฟล์ `.env` สำหรับทดสอบในเครื่องตัวเอง:**
   ```env
   GEMINI_API_KEY=ใส่_API_KEY_ที่สมัครฟรีจาก_Google_AI_Studio
   ```

---

## 📄 3. ข้อมูลตัวอย่างสำหรับทดสอบ (`input/tasks.json`)
ให้สร้างไฟล์นี้ไว้ในโฟลเดอร์ `input/tasks.json` เพื่อจำลองโจทย์จริงของกรรมการ:
```json
[
  {
    "task_id": "v1",
    "video_url": "https://storage.googleapis.com/amd-hackathon-clips/1860079-uhd_2560_1440_25fps.mp4",
    "styles": ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]
  },
  {
    "task_id": "v2",
    "video_url": "https://storage.googleapis.com/amd-hackathon-clips/13825391-uhd_3840_2160_30fps.mp4",
    "styles": ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]
  }
]
```

---

## 🐍 4. โค้ดตั้งต้นภาษา Python (Code Boilerplate)

นี่คือโค้ดตัวอย่างที่ใช้ไลบรารีอย่างเป็นทางการของ Google (`google-genai`) ในการส่งไฟล์วิดีโอไปประมวลผล

### สคริปต์ดึงและดาวน์โหลดไฟล์วิดีโอ (`src/downloader.py`)
```python
import os
import requests

def download_video(url: str, output_dir: str = "temp_videos") -> str:
    """ดาวน์โหลดวิดีโอจาก URL มาเก็บไว้ในเครื่องชั่วคราว"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    filename = url.split('/')[-1]
    local_path = os.path.join(output_dir, filename)
    
    # ถ้ามีไฟล์อยู่แล้ว ไม่ต้องโหลดซ้ำตอนกำลังเทส
    if os.path.exists(local_path):
        print(f"[-] File already exists: {local_path}")
        return local_path
        
    print(f"[*] Downloading {url} -> {local_path}")
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    
    with open(local_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                
    print("[+] Download complete!")
    return local_path
```

### สคริปต์เชื่อมต่อและวิเคราะห์วิดีโอด้วย Gemini (`src/pipeline.py`)
```python
import os
import json
import time
from google import genai
from google.genai import types

def generate_captions(video_path: str, prompt: str) -> dict:
    """อัปโหลดวิดีโอขึ้น Gemini API และรอรับผลลัพธ์ในรูปแบบ JSON"""
    # โหลด API Key จากตัวแปรระบบ
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY environment variable")
        
    client = genai.Client(api_key=api_key)
    
    print(f"[*] Uploading video to Gemini API: {video_path}")
    # อัปโหลดไฟล์วิดีโอขึ้นระบบคลาวด์ชั่วคราวของ Gemini
    video_file = client.files.upload(file=video_path)
    print(f"[+] Uploaded! File Name: {video_file.name}")
    
    # วิดีโอขนาดใหญ่ต้องการเวลาในการประมวลผลในฝั่ง Google เสมอ (ต้องรอจนกว่าสถานะจะเป็น ACTIVE)
    while video_file.state.name == "PROCESSING":
        print("[.] Waiting for video processing on Google side...")
        time.sleep(5)
        video_file = client.files.get(name=video_file.name)
        
    if video_file.state.name == "FAILED":
        raise ValueError(f"Video processing failed on Google: {video_file.error.message}")
        
    print("[+] Video is active! Sending generation request...")
    
    # รันโมเดล Gemini 2.5 Flash และบังคับให้ออกผลลัพธ์เป็น JSON โครงสร้างตามสั่ง
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[video_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.7
        )
    )
    
    # ลบไฟล์ออกจาก Google Storage ทันทีหลังใช้งานเพื่อความสะอาด
    client.files.delete(name=video_file.name)
    print("[+] Cleaned up cloud file.")
    
    # แปลงคำตอบสตริงให้เป็น Dictionary
    try:
        result_json = json.loads(response.text)
        return result_json
    except json.JSONDecodeError:
        print("[!] Warning: AI returned invalid JSON. Raw response:")
        print(response.text)
        return {"error": "Malformed JSON returned from AI", "raw": response.text}
```

### สคริปต์หลักที่เป็นตัววิ่งระบบ (`src/main.py`)
```python
import os
import json
from dotenv import load_dotenv
from downloader import download_video
from pipeline import generate_captions

# โหลดตัวแปรสภาพแวดล้อม (.env) สำหรับ Local Dev
load_dotenv()

PROMPT_TEMPLATE = """
Watch this video carefully and generate 4 different captions based on the scene:
1. FORMAL: Objective and factual tone.
2. SARCASTIC: Dry, ironic and mocking tone.
3. HUMOROUS_TECH: Funny with programming/IT references.
4. HUMOROUS_NON_TECH: Everyday humor, sitcom-style jokes.

Format output as JSON with keys matching the styles requested.
"""

def main():
    input_path = "/input/tasks.json" if os.path.exists("/input/tasks.json") else "input/tasks.json"
    output_path = "/output/results.json" if os.path.exists("/output") else "output/results.json"
    
    # สร้างโฟลเดอร์ Output หากไม่มี (กรณีเทสบนเครื่องตัวเอง)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"[*] Reading tasks from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        tasks = json.load(f)
        
    results = []
    
    for task in tasks:
        task_id = task["task_id"]
        video_url = task["video_url"]
        
        print(f"\n[=== Processing Task: {task_id} ===]")
        try:
            # 1. ดาวน์โหลดวิดีโอลงเครื่อง
            local_video = download_video(video_url)
            
            # 2. ส่งวิเคราะห์และเจนแคปชัน
            captions = generate_captions(local_video, PROMPT_TEMPLATE)
            
            # 3. เตรียมโครงสร้างคำตอบ
            results.append({
                "task_id": task_id,
                "captions": captions
            })
            
            # ลบไฟล์วิดีโอตัวเต็มหลังทำเสร็จทันทีเพื่อประหยัดพื้นที่ดิสก์ใน Docker
            if os.path.exists(local_video):
                os.remove(local_video)
                print(f"[+] Deleted local file: {local_video}")
                
        except Exception as e:
            print(f"[🔴 Error in Task {task_id}]: {str(e)}")
            # ใส่ Fallback เผื่อสคริปต์พัง เพื่อให้มีส่งผลลัพธ์ครบทุกตัว
            results.append({
                "task_id": task_id,
                "captions": {
                    "formal": "Error processing this video.",
                    "sarcastic": "Error processing this video.",
                    "humorous_tech": "Error processing this video.",
                    "humorous_non_tech": "Error processing this video."
                }
            })
            
    # เขียนผลลัพธ์กลับลง results.json
    print(f"\n[*] Writing results to {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print("[🎉] Pipeline executed successfully!")

if __name__ == "__main__":
    main()
```

---

## 🐋 5. ตัวอย่างไฟล์ Dockerfile (`Dockerfile`)
วางตัวอย่างไฟล์โครงร่างสำหรับประกอบส่งท้ายสัปดาห์:
```dockerfile
FROM python:3.11-slim

# อัปเดตและติดตั้ง FFmpeg สำหรับงานตัดต่อไฟล์เสียง
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกซอร์สโค้ดและโปรมพ์ต่างๆ เข้าตู้คอนเทนเนอร์
COPY src/ ./src/

ENV PYTHONUNBUFFERED=1

# สั่งให้รัน main.py อัตโนมัติทันทีที่กรรมการสตาร์ท Docker
CMD ["python", "src/main.py"]
```
