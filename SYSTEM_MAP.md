# 🗺️ POE2 Booster — System Map & Index (สารบัญระบบ)

สารบัญนี้จัดทำขึ้นเพื่อแสดงโครงสร้างไฟล์และรายละเอียดสถาปัตยกรรมของโปรเจกต์อย่างกระชับ เพื่อใช้อ่านศึกษาและลดปริมาณ Token ที่ใช้ในบริบทของ AI ในการพัฒนาครั้งถัดไป

---

## 📁 โครงสร้างโปรเจกต์ (Project Directory Structure)

```
poe2-booster/
├── assets/                  # ไฟล์รูปภาพและไอคอนของระบบ
│   ├── logo.ico             # ไอคอนของโปรแกรม (.exe)
│   └── logo.png             # โลโก้ความละเอียดสูงสำหรับใช้แสดงผลใน UI
├── src/                     # โค้ดภาษา Python ทั้งหมด
│   ├── config.py            # การตั้งค่าระบบ, ธีมสี, และ Metadata
│   ├── booster.py           # ลอจิกการทำ Optimization และเขียน Config เกม
│   ├── main.py              # หน้ากากโปรแกรม (GUI) หลักและบริการพื้นหลัง
│   ├── updater.py           # ระบบเช็คเวอร์ชันดาวน์โหลดและติดตั้งตัวอัปเดต
│   └── wizard.py            # Setup Wizard รันเฉพาะเมื่อเปิดโปรแกรมครั้งแรก
├── dist/                    # โฟลเดอร์ที่เก็บไฟล์ .exe หลัง Compile
│   └── POE2Booster.exe      # ไฟล์โปรแกรมที่ Compile แล้ว (ส่งให้ผู้ใช้)
├── website/                 # โค้ดของหน้า Landing Page สำหรับโปรโมทแอป
├── build.spec               # ไฟล์คอนฟิก PyInstaller (ปัจจุบันไม่ได้ใช้แล้ว)
└── SYSTEM_MAP.md            # สารบัญระบบฉบับนี้
```

---

## ⚙️ หน้าที่ของแต่ละโมดูล (Module Reference)

### 1. 📝 `src/config.py` (175 lines)
*   **หน้าที่**: จัดเก็บ Metadata ธีมสีระบบ และการอ่าน/เขียนไฟล์การตั้งค่าผู้ใช้
*   **จุดสำคัญ**:
    *   `APP_VERSION`: เวอร์ชันปัจจุบันของแอป (เช่น `1.4.1`)
    *   `IS_PRO = True`: ปลดล็อกสิทธิ์ฟีเจอร์ทั้งหมดแบบฟรีถาวร
    *   `THEMES`: พาเลทสี 4 ธีม (blue, purple, amber, green)
    *   `save_config_file()` / `load_config()`: จัดการเซฟที่ `%APPDATA%/POE2Booster/config.json`

### 2. 🎮 `src/booster.py` (451 lines)
*   **หน้าที่**: ลอจิกการปรับปรุงระบบคอมพิวเตอร์และการปรับแต่งไฟล์เกม POE2
*   **จุดสำคัญ**:
    *   `get_poe2_config_optimizations()`: คืนค่าคอนฟิกภาพ/เสียง/เน็ตเวิร์กที่อัปเดตใหม่ล่าสุด (June 2026) เพื่อเขียนใส่ `production_Config.ini`
    *   `boost_all()`: ฟังก์ชันหลักที่รันงาน 5 อย่าง (ล้างแคช, ล้างแรม, ปรับ Priority เกม, ล้าง DNS, จัด Power Plan)
    *   `check_network_ping()`: วัดค่า Latency เน็ตเวิร์กไปยังเซิร์ฟเวอร์
    *   `get_gpu_stats()` / `clear_shader_cache()`: ดึงค่า GPU และสั่งล้างแคชกราฟิกของ POE2

### 3. 🖥️ `src/main.py` (1466 lines)
*   **หน้าที่**: ควบคุมหน้าต่าง GUI (Tkinter), แถบโปร่งใสด้านบนสุด (Overlay), หน้าบอร์ด Dashboard (Bento Grid) และรัน Thread ของบริการพื้นหลัง
*   **จุดสำคัญ**:
    *   `_is_frozen()`: เช็คสถานะตัวแปรเพื่อแยกระหว่างการรันผ่าน Python หรือไฟล์ `.exe` (ซัพพอร์ต Nuitka)
    *   `_do_boost()`: สั่งการ Boost และเรียกใช้ระบบอัปเดตเงียบทันทีหลัง Boost เสร็จหากมีเวอร์ชันใหม่
    *   `_silent_auto_update()`: โค้ดดาวน์โหลดและเรียกเขียน Batch script เพื่อสลับไฟล์และรีสตาร์ทตัวแปรอัตโนมัติ
    *   `_render_advanced_settings_tab()`: หน้าเปลี่ยนธีมสี เปิดปิด Auto-Boost, Auto-Clean, OBS Streamer Mode

### 4. 🔄 `src/updater.py` (220 lines)
*   **หน้าที่**: ตรวจสอบและดำเนินการอัปเดตผ่าน GitHub API แบบไร้หน้าต่างตอบโต้
*   **จุดสำคัญ**:
    *   `check_for_update()`: ดึงข้อมูล JSON จาก GitHub Releases ล่าสุดเพื่อเทียบ Tag
    *   `download_to_temp()`: ดาวน์โหลด `.exe` ตัวใหม่มาเซฟเป็น `_update_POE2Booster.exe`
    *   `apply_update_and_restart()`: เขียนและเรียกรันไฟล์ `.bat` ชั่วคราวเพื่อปิดกระบวนการหลัก ลบไฟล์เก่า สลับชื่อไฟล์ใหม่ แล้วรีสตาร์ทแอปกลับขึ้นมาทำงาน

### 5. 🧙 `src/wizard.py` (229 lines)
*   **หน้าที่**: หน้าต่างช่วยแนะนำการตั้งค่าครั้งแรกสุดเมื่อพบว่าแอปยังไม่มีไฟล์ config
*   **จุดสำคัญ**:
    *   สแกนหาไฟล์การตั้งค่าเกม และสแกนหาจุดคอขวดของเครื่องพร้อมแนะนำให้กด Boost ทันที 1 คลิก ก่อนเปิดแถบ Overlay จริง

---

## 🚀 สถาปัตยกรรมการ Compile เพื่อเลี่ยง Antivirus

*   **Compiler ที่ใช้**: **Nuitka** (แปลง Python → C → Native Executable)
*   **เหตุผล**: โค้ดที่ compile ผ่าน Nuitka เป็น C++ binary แท้ๆ ซึ่งจะไม่กระตุ้นให้ Windows Defender แจ้งเตือนแบบสุ่มเหมือน PyInstaller bootloader
*   **คำสั่งที่ใช้ Compile**:
    ```bash
    python -m nuitka --standalone --onefile --windows-console-mode=disable --windows-icon-from-ico=assets/logo.ico --include-data-dir=assets=assets --enable-plugin=tk-inter --assume-yes-for-download --output-dir=dist --output-filename=POE2Booster src/main.py
    ```

---

## 🛠️ ขั้นตอนการรัน Auto-Update
1. ตรวจพบอัปเดตจาก `check_for_update()` (เปรียบเทียบ Tag เวอร์ชัน เช่น `v1.4.1` กับ `v1.4.0`)
2. ดาวน์โหลดตัว `.exe` ตัวใหม่ผ่าน `download_to_temp()` ได้ไฟล์ชั่วคราว
3. สร้างสคริปต์สลับไฟล์ `_poe2booster_update.bat` รันสคริปต์แบบแอบซ่อน แล้วตัวหลักทำการปิดตัวเอง
4. สคริปต์ย้ายไฟล์ใหม่ทับไฟล์เก่า จากนั้นสั่งเปิดโปรแกรมขึ้นมาใหม่และลบตัวเองทิ้ง
