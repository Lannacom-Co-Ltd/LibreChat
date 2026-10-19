# CMUBS AI Hub — บันทึกโปรเจกต์

LibreChat ที่ปรับแต่งเป็น **CMUBS AI Hub** ให้คณะบริหารธุรกิจ มหาวิทยาลัยเชียงใหม่ (CMU Business School)
โดย Lannacom ไฟล์นี้สรุปกติกา โครงสร้าง และสิ่งที่ทำไปแล้ว เพื่อให้เริ่มงานต่อได้โดยไม่ต้องอธิบายใหม่
(อัปเดตล่าสุด 2026-10-19, branch `cmu-ai` ที่ `3fd315b31` + งาน Office Files ที่**ยังไม่ได้ commit**)

ติดตั้งบน server ใหม่ทั้งชุด: `DEPLOY.md`

## กติกาการทำงาน

- **Branch `cmu-ai` เท่านั้น** บน remote `lannacom` = https://github.com/Lannacom-Co-Ltd/LibreChat (repo สาธารณะ)
  ห้ามแตะหรือ push `main` และห้าม push ไป `origin` (upstream danny-avila/LibreChat)
- **Commit / push เมื่อผู้ใช้อนุมัติในรอบนั้นเท่านั้น** อนุมัติรอบก่อนไม่ครอบคลุมรอบถัดไป
- **ห้าม commit `.env`, `office.env`** (มี secret จริง) `docker-compose.override.yml` ถูก upstream ใส่ไว้ใน `.gitignore`
  จึงต้อง `git add -f docker-compose.override.yml`
- **repo สาธารณะ** ห้ามใส่ key, รหัสผ่าน, path ของ SSH key ในไฟล์ที่ commit
- **ขอบเขตงาน:** หน้า login (+ ชื่อระบบ ไอคอน คำทักทาย) และ **Office Files** (ให้ AI สร้างไฟล์) ส่วนอื่นของ LibreChat ไม่ยุ่ง
- **ไม่แก้ source ของ LibreChat และไม่แก้ image ของ office-docs** ทุกอย่างซ้อนทับตอนเปิด container
  (`docker-compose.override.yml` + `branding/`, `docker-compose.office.yml` + `office/`)
- ทุกครั้งที่แก้ CSS: `node branding/build-space-css.js` → เพิ่มเลข `space.css?v=N` ใน override →
  `docker compose -p librechat-main up -d --force-recreate api` → ทดสอบหลายขนาดจอทั้งสองธีม → ส่งภาพให้ผู้ใช้ดูก่อน commit
- ผู้ใช้สื่อสารภาษาไทย ชอบเห็นภาพตัวอย่างเทียบกันก่อนตัดสินใจ ชอบคำอธิบายง่ายๆ

## สภาพแวดล้อม

| ที่ | รายละเอียด |
|---|---|
| เครื่อง dev | Docker Compose ใน `C:\Users\dusitm\Documents\CMU-AI-Hub` **LibreChat ใช้ `-p librechat-main`** (volume เดิม), Office Files ใช้ `-p librechat-office -f docker-compose.office.yml -f docker-compose.office.dev.yml --env-file office.env` — LibreChat http://localhost:3080, Admin http://localhost:3000, MongoDB `127.0.0.1:27018`, ที่เก็บไฟล์ Office Files `127.0.0.1:9000`; คีย์ AI ตั้งเป็น `user_provided` (Claude ทดสอบในแชทเองไม่ได้) |
| Test server | https://ai.lanna.work ใน `/opt/librechat/cmu` (ไม่ใช่ git checkout) compose 3 ไฟล์ `-f docker-compose.yml -f docker-compose.override.yml -f docker-compose.lanna.yml` (project `cmu`, network `cmu_default`) + Office Files project `cmu-office`; Caddy + Cloudflare; โมเดลผ่าน OpenRouter (`modelSpecs` 6 ตัว) |
| Production | https://aihub.cmubs.cmu.ac.th — ยังไม่มี Office Files |

**Claude SSH เข้า test server ได้** (รายละเอียดใน `CLAUDE.local.md`) แต่ระบบตรวจสิทธิ์**บล็อกการแก้ไฟล์ของทีม**
(`librechat.yaml`, `Caddyfile`, `.env`, `docker-compose.override.yml`/`lanna.yml` บน server) และการอ่านข้อมูลผู้ใช้ใน MongoDB
→ เขียนคำสั่งให้ผู้ใช้รันเอง (สำรองไฟล์ก่อนแก้ทุกครั้ง) ส่วนไฟล์ของเรา (`office/`, `docker-compose.office.yml`, `office.env`),
`docker compose` ของ `cmu-office` และ `up -d --no-deps --force-recreate api` Claude ทำเองได้
ผู้ใช้วางข้อความยาวใน nano แล้วค้าง/ผิดบ่อย → ให้คำสั่งแบบ heredoc / python3 / sed ที่วางทีเดียวจบ

**หลังดึงโค้ดบน server ต้อง `up -d --force-recreate api` ห้ามใช้แค่ `restart`** — คำสั่งตอนเปิด container
ใส่ลิงก์ `space.css` ลง `index.html` เฉพาะตอนที่ยังไม่มี `restart` จึงค้างเวอร์ชันเก่า และ `restart` ไม่อ่าน `.env` ใหม่
Test server ยังใช้ branding รุ่นเก่ามาก (`space.css?v=14`) — Claude ไม่อัป branding เอง เป็นงานทีมตอนดึง `cmu-ai`

## Branding (หน้า login)

| ส่วน | กลไก |
|---|---|
| CSS หน้า login, คำทักทาย, ปุ่มดาวน์โหลดไฟล์ในแชท | `branding/space.css`, `branding/greeting.js` สร้างจาก `branding/build-space-css.js` (ห้ามแก้ไฟล์ที่สร้างออกมาโดยตรง) |
| โลโก้และไอคอน | `branding/build-icons.js` สร้าง `branding/icons/*` จาก `cmubs-logo.png` และ `cmu-logo.webp`; override mount ทับไฟล์ใน `/app/client/dist/assets/` |
| ใส่เข้า `index.html` | `command` ของ service `api` ใน override ใช้ `sed` ใส่ `<title>`, favicon `?v=3`, `lang.js?v=1`, `greeting.js?v=1`, `space.css?v=N` แล้ว `exec npm run backend` |
| Admin Panel | override ใช้ `sed` เปลี่ยนชื่อในไฟล์ bundle เป็น "CMUBS AI Hub Admin" + mount `favicon.ico`, `manifest.json` |
| ภาษาเริ่มต้น | `branding/lang.js` ตั้งภาษาอังกฤษถ้ายังไม่เคยเลือก |
| ขอบเขต CSS login | `div:has(> main)` ที่มีฟอร์ม login หรือมีปุ่ม `/oauth/` แต่ไม่มีฟอร์ม (โหมด SSO อย่างเดียว) — หน้าอื่นไม่โดน |
| ปุ่มดาวน์โหลด | `a[href*="/office-docs/"]` เป็นปุ่มพร้อมป้ายชนิดไฟล์ (DOCX/XLSX/PDF...) ทั้งสองธีม (`FILE_LINK` ใน build script) |

รายละเอียดไฟล์และวิธีเปลี่ยนแต่ละอย่างอยู่ใน `branding/README.md`

### สถานะดีไซน์ปัจจุบัน (`space.css?v=52`)

- **เลย์เอาต์:** โลโก้ + คำโปรยอยู่บน กล่อง login อยู่กลางจอพอดี ห้ามซ้อนกันทุกขนาดจอ (flex column + `order`, `min-height: 100svh`)
  ผู้ใช้ชอบระยะเดิม ห้ามเปลี่ยนระยะโดยไม่ถาม; มือถือ input 16px กัน iOS ซูม
- **พื้นหลัง:** ภาพตึกคณะ `branding/backdrops/dark.jpg` (เส้นขาวบนกรมท่า `#1a3b5e`) / `light.jpg` (เส้นฟ้าอมเขียวบนเทา `#e8e8e8`) ติดขอบล่าง
- **ธีมมืด:** ชั้นยิ่งบนยิ่งสว่าง พื้น → กล่อง → ปุ่ม/ช่องกรอก (แนวหน้า login ของ Claude), ตัวหนังสือขาว, กรอบโฟกัสขาว
- **ธีมสว่าง (แบบ C):** สีหลักฟ้าอมเขียวเข้ม `#145e6e` (หัวข้อ ตัวหนังสือปุ่ม ตัวอักษร CMU บนปุ่ม ขอบ เงา กรอบโฟกัส), ปุ่มขาว
- **ฟอนต์:** Montserrat (ฟอนต์เว็บคณะ) ทุกข้อความในหน้า login, ไฟล์ `branding/fonts/montserrat.woff2` (OFL);
  ภาษาไทยใช้ฟอนต์ของเครื่อง — ผู้ใช้ตัดสินใจไม่เปลี่ยนฟอนต์ไทยในหน้าเว็บ
- **หัวข้อ:** "Welcome to CMUBS AI Hub" / "ยินดีต้อนรับสู่ CMUBS AI Hub" ขนาดตามความกว้างกล่อง (`min(1.5rem, 7cqi)`) บรรทัดเดียวเสมอ
- **ปุ่ม SSO:** สูง 42px, ไอคอนคำว่า CMU (`icons/sso-dark.png` / `sso-light.png`) แทนไอคอน OpenID,
  ตัวหนังสือกึ่งหนา 13.5px บรรทัดเดียวตั้งแต่จอ 360px (จอ 320px ขึ้นสองบรรทัดโดยตั้งใจ)
- **คำทักทายหน้าแชทใหม่:** สุ่ม 8 แบบ EN/TH (`GREETINGS` ใน `build-space-css.js`, `librechat.yaml` `customWelcome: '{{user.name}}'`)

## Office Files (ให้ AI สร้างไฟล์)

LibreChat เรียก MCP ตัวเดียว `office-files` ที่ `http://office-docs:8959/mcp` เปิดไว้ทุกแชทผ่าน `mcpServers: ['office-files']`
ในทุก model spec; AI ถูกสั่งให้สร้างไฟล์เฉพาะตอนผู้ใช้ขอ ลิงก์สั้น `/office-docs/<token 16 ตัว>/<ชื่อ>` (~60–85 ตัวอักษร)
ไม่มีลายเซ็น bucket ให้คนนอกอ่านได้อย่างเดียว ไฟล์ถูกลบหลัง 24 ชม.

**Quality gate** (office-files): ทุกไฟล์ถูกตรวจก่อนส่งลิงก์ — แก้เองได้ก็แก้ (ป้ายกราฟทับ → แท่งนอน/legend,
หัวเรื่องซ้ำใน PDF, ตาราง ≥7 คอลัมน์ → แนวนอน, ลำดับ XML ใน Word, shape id ใน PowerPoint) ที่แก้ไม่ได้ส่งเป็น `PROBLEMS`
ให้ AI แก้และเรียกใหม่ในรอบเดียว (รูปโหลดไม่ได้, สูตร Excel ชี้เซลล์ว่าง, กล่องแผนภาพไม่เชื่อม, CSV คอลัมน์ไม่เท่ากัน);
เรียกผิดพารามิเตอร์ได้ error ที่บอกรายการพารามิเตอร์; ภาพตัวอย่างให้ AI ตรวจ (`PREVIEW_IMAGES`) **ปิดไว้** เพราะ LibreChat
ส่งรูปจากเครื่องมือให้ทุกโมเดล โมเดลที่อ่านได้แค่ข้อความ (DeepSeek) จะทำให้ทั้งคำขอล้ม; PDF ใช้ markdown-it (CommonMark+GFM)
เพราะ Python-Markdown ทำรายการย่อย 2 ช่องและตารางที่ไม่เว้นบรรทัดพัง; เครื่องมือรันใน thread pool → กราฟไม่ใช้ pyplot, PDF ใช้ lock
ทดสอบซ้ำด้วยสคริปต์ regression (กรณีที่เคยพัง 4 แบบ + ทุกเครื่องมือ) ผ่าน `docker exec -i office-docs python -`

| Container | ทำอะไร |
|---|---|
| `office-net` (`pause`) | ถือ network + alias `office-docs` ให้อีก 3 ตัวใช้ร่วม (localhost) — restart ตัวไหนก็ไม่หลุด |
| `office-files` (`office/files/`, build เอง) | ทางเข้าเดียว: `server.py` (เครื่องมือ + quality gate + proxy office-docs), `storage.py` (ลิงก์สั้น, สิทธิ์ bucket, ลบไฟล์เกิน `FILE_TTL_HOURS`=24), `pdf.py` (WeasyPrint + ภาพหน้าแรกด้วย pypdfium2), `charts.py` (matplotlib + ตรวจป้ายทับ), `diagrams.py` (Graphviz), `checks.py` (ตรวจ/ซ่อม docx/pptx/xlsx ด้วย lxml), `features.py` (เปิดปิดชนิดไฟล์ `OFFICE_WORD=off` ฯลฯ ใน `office.env` ค่าเริ่มต้น on; ชนิดที่ปิดไม่ถูกส่งให้ AI เลย ลด token) |
| `office-docs` (`georgx22/mcp-office-docs` ล็อก digest) | Word, Excel, PowerPoint, อีเมล .eml, XML, `cmubs_memo` (บันทึกข้อความ) |
| `office-storage` (`rustfs/rustfs:1.0.1`) | S3 เก็บไฟล์ (MinIO เลิกแจก image แล้ว) |

| ไฟล์ | หน้าที่ |
|---|---|
| `docker-compose.office.yml` + `office.env` | ชุดสำหรับ server (project `cmu-office`, network `LIBRECHAT_NETWORK`) |
| `docker-compose.office.dev.yml` | เครื่อง dev: ใช้ `docker-compose.office.yml` ตัวเดียวกับ server + เปิดพอร์ต 9000 ให้เบราว์เซอร์ (`-p librechat-office`, `office.env` ในเครื่อง) |
| `office/build-templates.py` | สร้าง `office/templates/*.docx/pptx` (รันใน image office-docs ตามหัวไฟล์) — Sarabun, th-TH, A4 ขอบราชการ, สีคณะ, โลโก้ทุกสไลด์, ฝังฟอนต์ใน Word, บันทึกข้อความ |
| `office/templates/custom_email_template.html` | หัว/ท้ายอีเมลของคณะ (เขียนมือ) |
| `office/config/*.yaml` | เครื่องมือ `cmubs_memo`, ค่า PowerPoint (`th-TH`) |
| `office/overlay/sitecustomize.py` | mount เข้า office-docs: ตัวหนา/ขนาดภาษาไทยใน Word (`bCs/iCs/szCs`), Excel เป็น Sarabun + สีคณะ, ดึงรูปกราฟจาก bucket ของเราภายใน (Cloudflare บล็อก Python และห้ามเปิด private SSRF) |
| `office/fonts/` | Sarabun (OFL) ใช้ทั้ง template และ image ของ office-files |
| `office/apply.sh` | ส่งค่าเปิดปิดชนิดไฟล์จาก `office.env` ในเครื่องขึ้น server (เฉพาะบรรทัด on/off, สำรองไฟล์เดิม) แล้ว recreate office-files + api; ที่อยู่ server อ่านจาก `OFFICE_REMOTE*` ใน `office.env` ในเครื่อง |

**ห้ามใส่ Office Files ใน `docker-compose.override.yml`** — production ใช้ไฟล์นี้ตรงจาก git ถ้ามี service ใหม่ในนั้น
production จะเปิดตามทันทีตอนทีมดึงโค้ด (ค่าแบบเครื่อง dev → พัง)
**`librechat.yaml` ใน git ไม่ใช่ไฟล์ที่ server ใช้** (server มีโมเดล/ค่าของทีม) — ส่วน MCP ในไฟล์ของเครื่อง dev ไม่ commit
(git จะขึ้น modified ตลอด เป็นปกติ); วิธีใส่บน server อยู่ใน `DEPLOY.md`
หลักทั่วไป: ทุกอย่างที่ commit ต้อง "ดึงไปแล้วไม่เปลี่ยนพฤติกรรม production" จนกว่าทีมจะตั้งใจเปิดใช้

ค่าที่ต้องมี: `OFFICE_DOCS_API_KEY` ต้องตรงกันใน `office.env` และ `.env` ของ LibreChat; `mcpSettings.allowedAddresses: ['office-docs:8959']`
ใน `librechat.yaml`; reverse proxy ส่ง `/office-docs/*` ไป `office-docs:9000` โดยรักษา Host header

## ระบบที่เก่งขึ้นจากการใช้งาน (`assistant/`)

ผู้ใช้อยากให้ AI "ยิ่งใช้ยิ่งเก่ง" เพราะอาจารย์ใช้ทำงานวิจัย — โมเดลไม่เรียนรู้จากแชท จึงทำเป็นชั้นความรู้รอบโมเดลที่ทีมดูแลปรับทุกเดือน
(รายละเอียดใน `assistant/README.md`): system prompt ของคณะ (`system-prompt.md` → `promptPrefix` ของทุก model spec ด้วย
`apply-system-prompt.py`), memory ส่วนตัว (เปิดอยู่แล้วบน server), Agent "ผู้ช่วยเขียนงานวิจัย" (`agents/research-writer.md`),
คลัง prompt 10 อัน (`prompts.md`), วงจร feedback 👍/👎 รายเดือน
**หลัก:** แชร์ "วิธีทำงาน" ไม่แชร์ "เนื้อหาวิจัย" ข้ามผู้ใช้, แชร์ด้วยความสมัครใจ, มีคนคัดกรอง (PDPA / จริยธรรมการวิจัย)
Agent และ Prompt ต้องสร้างผ่านหน้าเว็บโดยผู้ใช้ที่ login (Claude สร้างเองไม่ได้)

## การตั้งค่าบน server (`.env` ไม่อยู่ใน git)

```
APP_TITLE=CMUBS AI Hub
ALLOW_EMAIL_LOGIN=false                              # ลูกค้าขอให้ login ผ่าน SSO อย่างเดียว
OPENID_BUTTON_LABEL=Continue with CMU IT Account
ALLOW_REGISTRATION=false
OFFICE_DOCS_API_KEY=<เท่ากับใน office.env>
```

ห้ามตั้ง `ALLOW_EMAIL_LOGIN=false` บนเครื่อง dev เพราะไม่มี SSO จะ login ไม่ได้ —
ทดสอบโหมด SSO อย่างเดียวด้วยการจำลองใน browser (ลบฟอร์ม ใส่ปุ่ม `/oauth/openid` ที่มี `svg#openid`)

Test server: `balance.enabled: false` (ทีมให้ปิดได้; ค่าเดิม start/refill 1,000,000 ต่อวัน ≈ $1) — production ควรเปิด
สำรองไฟล์ของทีมก่อนแก้ไว้ใน `/opt/librechat/cmu/backup-office-*` และ `librechat.yaml.before-*`

## สถานะล่าสุดและงานค้าง

- **ยังไม่ได้ commit งาน Office Files ทั้งหมด** (`office/`, `docker-compose.office.yml`, override, `DEPLOY.md`,
  `branding/build-space-css.js` + `space.css` v=52, ไฟล์นี้) — รอผู้ใช้อนุมัติ
- **เอกสารสำหรับลูกค้า** (2026-10-08 ถึง 10-16): `CAPABILITIES.md` (รายการความสามารถ), `SOLUTION.md` (แนวทางและค่าใช้จ่าย Sonnet 5 / GPT-5.6 Terra,
  เครื่องมือเสริม 12 รายการ, ชุดข้อเสนอ 4 ชุด) และ PDF/PPTX ที่ root; `email-2026-10-09/`, `email-2026-10-10/` = อีเมลและไฟล์ตัวอย่างที่ส่งลูกค้า
- ผู้ใช้ยังไม่ยืนยันในแชทจริง: PowerPoint หลังแก้ shape id, บันทึกข้อความ, กราฟ/แผนภาพใน Word, ปุ่มดาวน์โหลด
- **สร้างภาพด้วย AI:** รอเลือกผู้ให้บริการ (แนะนำ Gemini หรือ Azure ผ่าน Foundry) และวงเงินต่อคน
  แผนคือเพิ่ม `create_image` ใน office-files (ไม่ใช่ Agent) ผู้ใช้ใส่ key เองใน `office.env`
- Production (เช็ค 2026-10-08): หน้า login ตรงกับ `cmu-ai` ล่าสุดบน GitHub (`v=50`, hash `space.css`/`greeting.js`/`lang.js` ตรงกัน),
  ปิดอีเมล login แล้ว, ยังไม่มี Office Files; test server ยังเป็น branding `v=14` (ไฟล์ลงวันที่ 2026-09-25) แต่มี Office Files ล่าสุด
- **Azure AI Foundry:** รอรายละเอียดจากพี่ในทีม มี template ที่ comment ไว้ใน `librechat.yaml`
- ยังไม่ได้ยืนยันบน iPhone จริงว่าหน้า login ไม่เด้งขึ้นลงแล้ว (แก้ด้วย `100svh`)
- กล่องแจ้ง error สีแดงเข้มของ LibreChat ในธีมมืดยังไม่ได้ปรับ — ผู้ใช้บอกไม่ต้องสนใจฟอร์มอีเมล
- โฟลเดอร์ `undefined/` ที่ root ไม่ทราบที่มา ยังไม่ได้ลบ

## การทดสอบที่ใช้

หน้า login: `playwright-core` (มีใน `node_modules`) กับ Chrome ที่ติดตั้งในเครื่อง
(`C:/Program Files/Google/Chrome/Application/chrome.exe`) ตรวจทุกครั้งที่แก้:

- 26 ขนาดจอ (มือถือ แท็บเล็ต จอคอม จอเตี้ย จอกว้าง) ทั้งมี/ไม่มีปุ่ม SSO: ไม่ซ้อน ไม่มีแถบเลื่อนแนวนอน กล่องอยู่กลางจอ
- โหมด SSO อย่างเดียว 7 ขนาดจอ × 2 ธีม: ธีมขึ้น โลโก้ถูก ปุ่มกดได้
- หัวข้อและข้อความปุ่มอยู่บรรทัดเดียว (เทียบ `scrollWidth`/ความสูง) ตั้งแต่ 320px ถึง 1440px ทั้ง EN/TH
- ฟอนต์ที่แสดงผลจริงผ่าน CDP `CSS.getPlatformFontsForNode`
- เทียบกับ production: hash ไฟล์ `/assets/custom/*` กับ `git show HEAD:branding/...` (ไม่นับ CRLF)

Office Files (ไม่ต้อง login): สคริปต์ Python ที่ใช้ `fastmcp.Client` รันด้วย `docker exec -i office-docs python -`
(บน server: `ssh ... 'sudo docker exec -i cmu-office-docs python -'`) เรียกเครื่องมือที่ `http://localhost:8959/mcp`
พร้อม `Authorization: Bearer $API_KEY` แล้ว `curl` ลิงก์ที่ได้ (Cloudflare บล็อก Python urllib — ใช้ curl)

- ดูหน้าตาไฟล์: image `lo-preview` (debian + LibreOffice writer/impress + poppler) แปลงเป็น PDF → `pdftoppm` เป็น PNG
  — **LibreOffice ใจดีกว่า Word/PowerPoint** ต้องตรวจ XML เพิ่ม: ลำดับลูกของ `w:rPr`/`w:pPr`/`w:tblPr` ตาม schema,
  shape id ใน pptx ต้องต่ำกว่า 2^31, ฟอนต์ฝังใน `word/fonts/`
- ทดสอบความทนทาน: `docker restart office-docs` แล้วเรียกทุกเครื่องมือซ้ำ

## เรื่องที่เคยพลาด

- โปรเจกต์ย้ายจาก `Documents\LibreChat-main` มา `Documents\CMU-AI-Hub` เมื่อ 2026-10-08:
  container เดิมยังผูก path เก่า Docker จึงสร้างโฟลเดอร์ว่างแทนไฟล์ที่ mount และ container พัง
  ต้องลบ container เดิมแล้ว `up -d` จากโฟลเดอร์ใหม่ด้วย `-p librechat-main` (ทำแล้ว)
- เคยสร้าง repo แยก `Lannacom-Co-Ltd/cmu-ai` และ branch `brand/cmu-ai` โดยผิดความต้องการ — ผู้ใช้ต้องการ repo เดียว branch `cmu-ai` เท่านั้น
- Template literal ใน `build-space-css.js` ห้ามมี backtick ในคอมเมนต์
- `sharp`: trim ก่อน extract ใน pipeline เดียวไม่ได้ ต้องแยกสองขั้น
- **Office Files:**
  - ชื่อไฟล์ภาษาไทยทำให้ลิงก์ยาว AI คัดลอกไม่ครบ/พิมพ์ใหม่ → `AccessDenied`/`SignatureDoesNotMatch`;
    แก้ด้วยคำสั่งให้ใช้ชื่ออังกฤษ และ office-files ใช้ key ASCII (ชื่อไทยอยู่ใน Content-Disposition)
  - office-docs ตัดสระ/วรรณยุกต์ไทยออกจากชื่อไฟล์ (`\w` ไม่รวม Mn)
  - ผู้ใช้สร้าง `office.env` ใหม่ทับ → คีย์ไม่ตรง LibreChat ต่อ MCP ไม่ได้ (`invalid or missing API key`)
  - ผู้ใช้วางคำสั่ง reload ลงใน `Caddyfile` → config เสีย (Caddy ใช้ config เก่าต่อจนกว่าจะ restart)
  - LibreChat ยิง HEAD โดยไม่มี key ถ้าได้ 401 จะคิดว่าเป็น OAuth → office-files ปล่อย HEAD/well-known ผ่าน
  - python-pptx ให้ shape id ≥ 2^31 กับรูปที่เพิ่มใน slide master → PowerPoint เปิดไม่ได้
  - python-docx ตั้งแค่ `w:b`/`w:sz` → ภาษาไทยไม่หนา/ไม่เปลี่ยนขนาด
  - `network_mode: service:office-docs` เดิม: office-docs restart แล้วตัวอื่นหลุด network → เปลี่ยนเป็น `office-net`
  - Graphviz เว้นบรรทัดตามขนาดฟอนต์ สระบนไทยชนบรรทัดบน → ป้ายหลายบรรทัดใช้ HTML table แถวละบรรทัด
  - เขียน Python ที่มี `\n` ผ่าน bash heredoc แล้ว escape เพี้ยน → เขียนสคริปต์ patch เป็นไฟล์ด้วย Write แทน
  - ลิงก์ presigned ยาว ~320 ตัว AI พิมพ์เพี้ยนได้เสมอ (path ซ้ำ, ถอดรหัสไทย) → เปลี่ยนเป็นลิงก์สั้นไม่มีลายเซ็น
  - ข้อความเตือนของ office-docs มีลิงก์รูปที่หายปนอยู่ ตัวย้ายลิงก์ต้องย้ายเฉพาะลิงก์ที่มี `X-Amz-Signature`
  - แก้ XML ของ docx ด้วย ElementTree จะทิ้ง namespace ที่ `mc:Ignorable` อ้าง → ใช้ lxml
