# CMUBS AI Hub — บันทึกโปรเจกต์

LibreChat ที่ปรับแต่งเป็น **CMUBS AI Hub** ให้คณะบริหารธุรกิจ มหาวิทยาลัยเชียงใหม่ (CMU Business School)
โดย Lannacom ไฟล์นี้สรุปกติกา โครงสร้าง และสิ่งที่ทำไปแล้ว เพื่อให้เริ่มงานต่อได้โดยไม่ต้องอธิบายใหม่
(อัปเดตล่าสุด 2026-10-08, branch `cmu-ai` ที่ `312b5b6b6`)

## กติกาการทำงาน

- **Branch `cmu-ai` เท่านั้น** บน remote `lannacom` = https://github.com/Lannacom-Co-Ltd/LibreChat (repo สาธารณะ)
  ห้ามแตะหรือ push `main` และห้าม push ไป `origin` (upstream danny-avila/LibreChat)
- **Commit / push เมื่อผู้ใช้อนุมัติในรอบนั้นเท่านั้น** อนุมัติรอบก่อนไม่ครอบคลุมรอบถัดไป
- **ห้าม commit `.env`** (มี secret จริง) `docker-compose.override.yml` ถูก upstream ใส่ไว้ใน `.gitignore`
  จึงต้อง `git add -f docker-compose.override.yml`
- **หน้าที่จบที่โค้ด** แก้บน localhost แล้ว push `cmu-ai` การดึงโค้ดขึ้น server เป็นงานของคนอื่น
  ไม่ต้องใส่ขั้นตอน deploy ท้ายคำตอบ เว้นแต่ถูกถาม
- **ขอบเขตคือหน้า login** ส่วนอื่นของ LibreChat ไม่ยุ่ง (ยกเว้นชื่อระบบ ไอคอน คำทักทายหน้าแชทใหม่ ที่ทำไว้แล้ว)
- **ไม่แก้ source ของ LibreChat** ทุกอย่างซ้อนทับตอนเปิด container ผ่าน `docker-compose.override.yml` + `branding/`
- ทุกครั้งที่แก้ CSS: `node branding/build-space-css.js` → เพิ่มเลข `space.css?v=N` ใน override → 
  `docker compose up -d --force-recreate api` → ทดสอบหลายขนาดจอทั้งสองธีม → ส่งภาพให้ผู้ใช้ดูก่อน commit
- ผู้ใช้สื่อสารภาษาไทย ชอบเห็นภาพตัวอย่างเทียบกันก่อนตัดสินใจ

## สภาพแวดล้อม

| ที่ | รายละเอียด |
|---|---|
| เครื่อง dev | Docker Compose เท่านั้น ใน `C:\Users\dusitm\Documents\CMU-AI-Hub` (ย้ายมาจาก `LibreChat-main`) — LibreChat http://localhost:3080, Admin Panel http://localhost:3000, MongoDB `127.0.0.1:27018` (สำหรับ Compass) |
| Test server | https://ai.lanna.work (Azure VM 20.188.114.63) ใน `/opt/librechat/cmu` — ไม่ใช่ git checkout, ใช้ compose 3 ไฟล์ `-f docker-compose.yml -f docker-compose.override.yml -f docker-compose.lanna.yml`; `librechat.yaml` และ `docker-compose.lanna.yml` บน server เป็นของพี่ในทีม ห้ามทับ |
| Production | https://aihub.cmubs.cmu.ac.th (104.214.187.76) |

Claude เข้า server ไม่ได้ ผู้ใช้หรือทีมเป็นคนรันคำสั่งบน server เช็คจากภายนอกได้ด้วย
`curl https://aihub.cmubs.cmu.ac.th/api/config` และดูเลข `space.css?v=` ใน `/login`

**หลังดึงโค้ดบน server ต้อง `up -d --force-recreate api` ห้ามใช้แค่ `restart`** — คำสั่งตอนเปิด container
ใส่ลิงก์ `space.css` ลง `index.html` เฉพาะตอนที่ยังไม่มี `restart` จึงค้างเวอร์ชันเก่า และ `restart` ไม่อ่าน `.env` ใหม่

## การปรับแต่งทำงานอย่างไร

| ส่วน | กลไก |
|---|---|
| CSS หน้า login, คำทักทาย | `branding/space.css`, `branding/greeting.js` สร้างจาก `branding/build-space-css.js` (ห้ามแก้ไฟล์ที่สร้างออกมาโดยตรง) |
| โลโก้และไอคอน | `branding/build-icons.js` สร้าง `branding/icons/*` จาก `cmubs-logo.png` และ `cmu-logo.webp`; override mount ทับไฟล์ใน `/app/client/dist/assets/` |
| ใส่เข้า `index.html` | `command` ของ service `api` ใน override ใช้ `sed` ใส่ `<title>`, favicon `?v=3`, `lang.js?v=1`, `greeting.js?v=1`, `space.css?v=N` แล้ว `exec npm run backend` |
| Admin Panel | override ใช้ `sed` เปลี่ยนชื่อในไฟล์ bundle เป็น "CMUBS AI Hub Admin" + mount `favicon.ico`, `manifest.json` |
| ภาษาเริ่มต้น | `branding/lang.js` ตั้งภาษาอังกฤษถ้ายังไม่เคยเลือก |
| ขอบเขต CSS | `div:has(> main)` ที่มีฟอร์ม login หรือมีปุ่ม `/oauth/` แต่ไม่มีฟอร์ม (โหมด SSO อย่างเดียว) — หน้าอื่นไม่โดน |

รายละเอียดไฟล์และวิธีเปลี่ยนแต่ละอย่างอยู่ใน `branding/README.md`

## สถานะดีไซน์ปัจจุบัน (`space.css?v=50`)

- **เลย์เอาต์:** โลโก้ + คำโปรยอยู่บน กล่อง login อยู่กลางจอพอดี ห้ามซ้อนกันทุกขนาดจอ (flex column + `order`, `min-height: 100svh`)
  ผู้ใช้ชอบระยะเดิม ห้ามเปลี่ยนระยะโดยไม่ถาม; มือถือ input 16px กัน iOS ซูม
- **พื้นหลัง:** ภาพตึกคณะ `branding/backdrops/dark.jpg` (เส้นขาวบนกรมท่า `#1a3b5e`) / `light.jpg` (เส้นฟ้าอมเขียวบนเทา `#e8e8e8`) ติดขอบล่าง
- **ธีมมืด:** ชั้นยิ่งบนยิ่งสว่าง พื้น → กล่อง → ปุ่ม/ช่องกรอก (แนวหน้า login ของ Claude), ตัวหนังสือขาว, กรอบโฟกัสขาว
- **ธีมสว่าง (แบบ C):** สีหลักฟ้าอมเขียวเข้ม `#145e6e` (หัวข้อ ตัวหนังสือปุ่ม ตัวอักษร CMU บนปุ่ม ขอบ เงา กรอบโฟกัส), ปุ่มขาว
- **ฟอนต์:** Montserrat (ฟอนต์เว็บคณะ) ทุกข้อความในหน้า login, ไฟล์ `branding/fonts/montserrat.woff2` (OFL);
  ภาษาไทยใช้ฟอนต์ของเครื่อง — ผู้ใช้ตัดสินใจไม่เปลี่ยนฟอนต์ไทย
- **หัวข้อ:** "Welcome to CMUBS AI Hub" / "ยินดีต้อนรับสู่ CMUBS AI Hub" ขนาดตามความกว้างกล่อง (`min(1.5rem, 7cqi)`) บรรทัดเดียวเสมอ
- **ปุ่ม SSO:** สูง 42px, ไอคอนคำว่า CMU (`icons/sso-dark.png` / `sso-light.png`) แทนไอคอน OpenID,
  ตัวหนังสือกึ่งหนา 13.5px บรรทัดเดียวตั้งแต่จอ 360px (จอ 320px ขึ้นสองบรรทัดโดยตั้งใจ)
- **คำทักทายหน้าแชทใหม่:** สุ่ม 8 แบบ EN/TH (`GREETINGS` ใน `build-space-css.js`, `librechat.yaml` `customWelcome: '{{user.name}}'`)

## การตั้งค่าบน server (`.env` ไม่อยู่ใน git)

```
APP_TITLE=CMUBS AI Hub
ALLOW_EMAIL_LOGIN=false                              # ลูกค้าขอให้ login ผ่าน SSO อย่างเดียว
OPENID_BUTTON_LABEL=Continue with CMU IT Account
ALLOW_REGISTRATION=false
```

ห้ามตั้ง `ALLOW_EMAIL_LOGIN=false` บนเครื่อง dev เพราะไม่มี SSO จะ login ไม่ได้ —
ทดสอบโหมด SSO อย่างเดียวด้วยการจำลองใน browser (ลบฟอร์ม ใส่ปุ่ม `/oauth/openid` ที่มี `svg#openid`)

## สถานะล่าสุดและงานค้าง

- Production ตั้ง `.env` แล้ว (ฟอร์มอีเมลหายแล้ว) แต่เมื่อเช็คล่าสุดยังเป็นโค้ด `v=41` —
  รอทีม server ดึง `cmu-ai` ล่าสุดแล้ว `--force-recreate api`
- **Azure AI Foundry:** รอรายละเอียดจากพี่ในทีม (endpoint, deployment, api-version, embedding)
  มี template ที่ comment ไว้ใน `librechat.yaml` แล้ว ผู้ใช้ต้องใส่ API key เอง
- ยังไม่ได้ยืนยันบน iPhone จริงว่าหน้า login ไม่เด้งขึ้นลงแล้ว (แก้ด้วย `100svh`)
- กล่องแจ้ง error สีแดงเข้มของ LibreChat ในธีมมืดยังไม่ได้ปรับ — ผู้ใช้บอกไม่ต้องสนใจฟอร์มอีเมล

## การทดสอบที่ใช้

ใช้ `playwright-core` (มีใน `node_modules`) กับ Chrome ที่ติดตั้งในเครื่อง
(`C:/Program Files/Google/Chrome/Application/chrome.exe`) ตรวจทุกครั้งที่แก้:

- 26 ขนาดจอ (มือถือ แท็บเล็ต จอคอม จอเตี้ย จอกว้าง) ทั้งมี/ไม่มีปุ่ม SSO: ไม่ซ้อน ไม่มีแถบเลื่อนแนวนอน กล่องอยู่กลางจอ
- โหมด SSO อย่างเดียว 7 ขนาดจอ × 2 ธีม: ธีมขึ้น โลโก้ถูก ปุ่มกดได้
- หัวข้อและข้อความปุ่มอยู่บรรทัดเดียว (เทียบ `scrollWidth`/ความสูง) ตั้งแต่ 320px ถึง 1440px ทั้ง EN/TH
- ฟอนต์ที่แสดงผลจริงผ่าน CDP `CSS.getPlatformFontsForNode`
- เทียบกับ production: hash ไฟล์ `/assets/custom/*` กับ `git show HEAD:branding/...` (ไม่นับ CRLF)

## เรื่องที่เคยพลาด

- โปรเจกต์ย้ายจาก `Documents\LibreChat-main` มา `Documents\CMU-AI-Hub` เมื่อ 2026-10-08:
  container เดิมยังผูก path เก่า Docker จึงสร้างโฟลเดอร์ว่างแทนไฟล์ที่ mount (เช่น `.env/` เป็นโฟลเดอร์) และ container พัง
  ต้องลบ container เดิมแล้ว `up -d` จากโฟลเดอร์ใหม่ (ระวัง named volume ผูกกับชื่อ project — ใช้ `-p librechat-main` ถ้าจะใช้ volume เดิม)
- เคยสร้าง repo แยก `Lannacom-Co-Ltd/cmu-ai` และ branch `brand/cmu-ai` โดยผิดความต้องการ — ผู้ใช้ต้องการ repo เดียว branch `cmu-ai` เท่านั้น
- Template literal ใน `build-space-css.js` ห้ามมี backtick ในคอมเมนต์
- `sharp`: trim ก่อน extract ใน pipeline เดียวไม่ได้ ต้องแยกสองขั้น
