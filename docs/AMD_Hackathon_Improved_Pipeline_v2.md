# AMD Hackathon Track 2 - Improved Pipeline (Version 2.0)

## Pipeline

``` text
1. Read tasks.json
2. Download Video
3. FFmpeg
   ├─ Extract Audio
   └─ Extract Key Frames
4. Scene Segmentation
5. Multimodal Analysis
   ├─ Vision Analysis (Gemini)
   ├─ Speech Transcription
   └─ Ambient Sound Analysis
6. Object Memory Builder
7. Rich Scene Description
8. Generate 4 Captions
9. Diversity Check
10. Gemma Refinement
11. Self Critique Loop
12. JSON Validation
13. Save results.json
14. Exit Code 0
```

## Improvements

### 1. Scene Segmentation

-   แบ่งวิดีโอเป็นหลายช่วงก่อนส่งเข้า Gemini
-   วิเคราะห์แต่ละฉากแยกกัน
-   รวมผลเป็นภาพรวมของคลิป
-   ช่วยให้เข้าใจคลิปยาวและเหตุการณ์ต่อเนื่องได้แม่นยำขึ้น

### 2. Object Memory

สร้างหน่วยความจำเก็บข้อมูลสำคัญระหว่างการวิเคราะห์ เช่น - ตัวละคร - วัตถุ -
การกระทำ - สีเสื้อ - สิ่งของเด่น

ตัวอย่าง

``` python
object_memory = {
    "people": [],
    "objects": [],
    "actions": []
}
```

ใช้ข้อมูลเหล่านี้ช่วยสร้าง Caption ที่อ้างอิงรายละเอียดจริงในคลิป

### 3. Caption Diversity Check

ตรวจสอบว่า Caption ทั้ง 4 แบบแตกต่างกันจริง

หาก Similarity มากกว่า 70% - Regenerate Caption -
เพิ่มความแตกต่างของโครงสร้างและมุก - ลดการใช้ข้อความซ้ำ

### 4. Parallel Processing

ประมวลผลหลายคลิปพร้อมกัน

เช่น - ดาวน์โหลดคลิปถัดไป - Gemini วิเคราะห์คลิปก่อนหน้า - เตรียมไฟล์เสียงของอีกคลิป

เพื่อลดเวลารวมของระบบ

### 5. Caption Quality Score

ประเมินหลายมิติ

``` json
{
  "relevance":9,
  "humor":8,
  "creativity":9,
  "clarity":10,
  "style_match":9
}
```

หากคะแนนด้านใดต่ำ ให้แก้เฉพาะด้านนั้นแทนการสร้างใหม่ทั้งหมด

### 6. Fallback Mode

หาก API หลักล้มเหลว

Gemini → Gemma → Template Caption

เพื่อให้ระบบสามารถส่งผลลัพธ์ได้ครบทุกคลิป

## Recommended Architecture

``` text
Input
 ↓
Download
 ↓
FFmpeg
 ├─ Audio
 ├─ Key Frames
 └─ Scene Split
 ↓
Gemini Vision
 ↓
Speech Analysis
 ↓
Object Memory
 ↓
Rich Description
 ↓
Caption Generation
 ↓
Diversity Check
 ↓
Gemma Refinement
 ↓
Self Critique
 ↓
JSON Validation
 ↓
Output
```

## Development Priority

1.  Object Memory
2.  Scene Segmentation
3.  Diversity Check
4.  Parallel Processing
5.  Quality Score Breakdown
6.  Fallback Mode

แนวทางนี้ช่วยเพิ่มทั้งคุณภาพของ Caption ความแตกต่างของแต่ละสไตล์ ความเสถียรของระบบ
และโอกาสรันครบทุกคลิปภายในเวลาที่กำหนดของการแข่งขัน
