# Lannacom AI Hub — ติดตั้งบน server ใหม่

คู่มือย้ายหรือติดตั้งระบบทั้งชุดบน server ใหม่ (เช่นจาก server ทดสอบของบริษัทไป server ของลูกค้า)
ครอบคลุมทุกอย่างที่ทำไว้ใน branch `new-AI-Hub`:

- **LibreChat** และการปรับแต่งหน้า login, ชื่อระบบ, ไอคอน, คำทักทาย (`branding/`, `docker-compose.override.yml`)
- **Office Files** ให้ AI สร้างไฟล์ Word, Excel, PowerPoint, PDF, ไฟล์ข้อความ, กราฟ, แผนภาพ, บันทึกข้อความ
  (`office/`, `docker-compose.office.yml`)

ไฟล์นี้อยู่ใน repo สาธารณะ **ห้ามใส่รหัสผ่าน, API key, IP หรือชื่อผู้ใช้ server จริง** ลงในไฟล์นี้

---

## 1. ภาพรวมระบบ

```
ผู้ใช้ ──https──▶ reverse proxy (Caddy) ──┬── /              ──▶ LibreChat (api:3080)
                                          └── /office-docs/* ──▶ office-docs:9000 (ไฟล์ให้ดาวน์โหลด)

LibreChat ──MCP──▶ office-docs:8959 (office-files) ──┬── PDF, ไฟล์ข้อความ, กราฟ, แผนภาพ (ทำเอง)
                                                    ├── Word/Excel/PowerPoint/อีเมล/บันทึกข้อความ ──▶ office-docs:8958
                                                    └── เก็บไฟล์ ──▶ office-storage:9000 (RustFS, S3)
```

| ส่วน | ไฟล์ / ที่มา | compose project |
|---|---|---|
| LibreChat, MongoDB, Meilisearch, RAG | `docker-compose.yml` (upstream) + `docker-compose.override.yml` (ของเรา) + ไฟล์ proxy/HTTPS ของ server | ของ LibreChat เช่น `aihub` |
| Office Files 4 container | `docker-compose.office.yml` + `office.env` | `aihub-office` แยกต่างหาก |

`office-net` เป็น container เปล่าที่ถือ network ให้ `office-files`, `office-docs`, `office-storage` ใช้ร่วมกัน
ชื่อ `office-docs` บน network ของ LibreChat จึงชี้ไปที่ทั้งชุด (พอร์ต 8958, 8959, 9000)

---

## 2. สิ่งที่ต้องเตรียมก่อน

| เรื่อง | รายละเอียด |
|---|---|
| Server | Linux ที่มี Docker Engine + Docker Compose v2, ผู้ใช้ที่ใช้ `sudo docker` ได้, ดิสก์ว่าง 20 GB ขึ้นไป |
| โดเมน | เช่น `aihub.<ลูกค้า>` ชี้มาที่ server, เปิดพอร์ต 80/443 |
| HTTPS | ใบรับรองของลูกค้า หรือให้ Caddy ออกให้อัตโนมัติ (Let's Encrypt) หรือ Cloudflare Origin Certificate |
| SSO (OpenID) | ลงทะเบียนแอปกับผู้ดูแล SSO ของลูกค้า: **Redirect URI** = `https://<โดเมน>/oauth/openid/callback` แล้วขอ Issuer URL, Client ID, Client Secret |
| AI | API key ของผู้ให้บริการโมเดล (ตอนนี้ใช้ OpenRouter) ในบัญชีของลูกค้า |
| Server ออกเน็ตได้ | ดึง image จาก Docker Hub และ `registry.librechat.ai`, และเรียก `https://<โดเมน>` ของตัวเองได้ (ดูข้อ 9) |

---

## 3. เอาโค้ดขึ้น server

แนะนำใช้ git checkout (server ทดสอบเดิมไม่ใช่ git ทำให้อัปเดตยาก)

```bash
sudo mkdir -p /opt/librechat && sudo chown $USER /opt/librechat
git clone -b new-AI-Hub https://github.com/Lannacom-Co-Ltd/LibreChat.git /opt/librechat/<ชื่อ>
cd /opt/librechat/<ชื่อ>
```

ไฟล์ที่ **ไม่อยู่ใน git** ต้องสร้างเองบน server: `.env`, `office.env`, `librechat.yaml` (ถ้าแยกของลูกค้า),
ไฟล์ proxy/HTTPS (`Caddyfile`, `docker-compose.<ลูกค้า>.yml`), ใบรับรอง

---

## 4. ตั้งค่า LibreChat (`.env`)

เริ่มจาก `cp .env.example .env` แล้วแก้ค่าตามนี้

**ต้องสร้างใหม่ทุก server (ห้ามคัดลอกจาก server อื่น):**

```bash
openssl rand -hex 32   # CREDS_KEY
openssl rand -hex 16   # CREDS_IV
openssl rand -hex 32   # JWT_SECRET
openssl rand -hex 32   # JWT_REFRESH_SECRET
openssl rand -hex 32   # MEILI_MASTER_KEY
openssl rand -hex 32   # OPENID_SESSION_SECRET
```

ถ้า **ย้ายข้อมูลผู้ใช้มาจาก server เดิม** ต้องใช้ `CREDS_KEY` / `CREDS_IV` ตัวเดิม ไม่อย่างนั้นอ่าน key ที่ผู้ใช้บันทึกไว้ไม่ได้

**ค่าของระบบนี้:**

```ini
APP_TITLE=Lannacom AI Hub
DOMAIN_CLIENT=https://<โดเมน>
DOMAIN_SERVER=https://<โดเมน>

# login ผ่าน SSO อย่างเดียว
ALLOW_EMAIL_LOGIN=false
ALLOW_REGISTRATION=false
ALLOW_SOCIAL_LOGIN=true
ALLOW_SOCIAL_REGISTRATION=true
OPENID_ISSUER=<จากผู้ดูแล SSO>
OPENID_CLIENT_ID=<จากผู้ดูแล SSO>
OPENID_CLIENT_SECRET=<จากผู้ดูแล SSO>
OPENID_SESSION_SECRET=<สุ่มด้านบน>
OPENID_SCOPE="openid profile email"
OPENID_CALLBACK_URL=/oauth/openid/callback
OPENID_BUTTON_LABEL=Continue with SSO

# AI
OPENROUTER_KEY=<key ของลูกค้า>

# Office Files: ต้องเท่ากับ OFFICE_DOCS_API_KEY ใน office.env (ข้อ 6)
OFFICE_DOCS_API_KEY=<ค่าเดียวกับใน office.env>
```

ก่อนปิดอีเมล login ให้แน่ใจว่า SSO ใช้ได้ ไม่อย่างนั้นจะไม่มีใครเข้าระบบได้ (รวมทั้งผู้ดูแล)

---

## 5. ตั้งค่า `librechat.yaml`

ใช้ไฟล์ใน repo เป็นต้นแบบ แล้วเพิ่ม endpoint/โมเดลของลูกค้า ส่วนที่ระบบนี้ต้องมี:

```yaml
interface:
  customWelcome: '{{user.name}}'      # คำทักทายหน้าแชทใหม่ (branding/greeting.js สุ่มประโยค)
  mcpServers:
    use: true

# Office Files อยู่ใน Docker network ซึ่ง LibreChat บล็อก MCP ไว้โดยค่าเริ่มต้น
mcpSettings:
  allowedAddresses:
    - 'office-docs:8959'

mcpServers:
  office-files:
    type: streamable-http
    url: http://office-docs:8959/mcp
    title: 'Office Files'
    description: 'Create downloadable files'
    headers:
      Authorization: 'Bearer ${OFFICE_DOCS_API_KEY}'
    timeout: 120000
    serverInstructions: true
    startup: true
    chatMenu: true

modelSpecs:
  list:
    - name: '<ชื่อโมเดล>'
      mcpServers: ['office-files']     # เปิด Office Files ไว้ทุกแชทใหม่ของโมเดลนี้
      label: '<ชื่อที่แสดง>'
      preset:
        endpoint: '<endpoint>'
        model: '<model id>'
```

ใส่ `mcpServers: ['office-files']` ให้ **ทุก** model spec ที่ต้องการให้สร้างไฟล์ได้ทันทีโดยไม่ต้องกดเลือก

**ห้ามใส่ข้อมูลผู้ใช้ (`{{LIBRECHAT_USER_*}}`) ใน headers ของ `office-files`** — LibreChat จะถือเป็นการเชื่อมต่อรายคน
และไม่โหลดเครื่องมือตอนเริ่ม ทำให้แชทจาก model spec ไม่มีเครื่องมือสร้างไฟล์เลย เครื่องมือผู้ดูแลจึงแยกเป็นอีก entry:

```yaml
  office-admin:                        # รายงานการใช้งาน + จัดการเครดิต (เฉพาะ ADMIN) ผู้ดูแลเลือกจากเมนู MCP ในแชท
    type: streamable-http
    url: http://office-docs:8959/mcp
    title: 'สำหรับผู้ดูแลระบบ - Admin only'   # ชื่อใช้ได้แค่ตัวอักษร ตัวเลข เว้นวรรค - และ ' (วงเล็บทำให้ LibreChat ไม่เปิด)
    description: 'เครดิตและรายงานการใช้งาน - Credits & usage report'
    headers:
      Authorization: 'Bearer ${OFFICE_DOCS_API_KEY}'
      X-AIHub-Scope: 'admin'
      X-User-Id: '{{LIBRECHAT_USER_ID}}'
      X-User-Role: '{{LIBRECHAT_USER_ROLE}}'
    timeout: 120000
    chatMenu: true
```

**เมนูโมเดลแยกตามค่ายพร้อมโลโก้** — ใส่ `group` (ชื่อค่าย), `iconURL` / `groupIcon` เป็น `/assets/custom/models/<ค่าย>.svg`
(ไฟล์อยู่ใน `branding/models/` สร้างด้วย `node branding/build-model-icons.js`) และ `artifacts: 'default'`, `skills: true`
ในแต่ละ spec เพื่อให้ Artifacts และ Skills ใช้ได้ในแชทของ spec นั้น ตั้ง `modelSpecs.addedEndpoints: ['agents']` เพื่อไม่ให้รายการรหัสโมเดลซ้ำ

**ถ้าใช้ Portkey เป็นทางผ่าน:** config ของ Portkey ต้อง**ไม่มี** `override_params.tools` (ถ้ามี Portkey จะแทนที่รายการเครื่องมือทั้งหมด
ทำให้ MCP, Skills, สร้างไฟล์ และ Agent ใช้ไม่ได้) และต้องเปิดสิทธิ์ทุกโมเดลในเมนูใน integration ไม่อย่างนั้นผู้ใช้จะรอหมุนราว 2 นาทีแล้วได้ error 412

---

## 6. ตั้งค่า Office Files (`office.env`)

สร้างครั้งเดียวต่อ server (**ห้ามรันซ้ำ** ถ้าสร้างใหม่ คีย์จะไม่ตรงกับ `.env` และ container ที่รันอยู่ ดูข้อ 10):

```bash
umask 077
cat > office.env <<EOF
OFFICE_DOCS_API_KEY=$(openssl rand -hex 32)
OFFICE_STORAGE_USER=officedocs
OFFICE_STORAGE_PASSWORD=$(openssl rand -hex 24)
OFFICE_PUBLIC_URL=https://<โดเมน>
OFFICE_FILE_TTL_HOURS=24
LIBRECHAT_NETWORK=<ชื่อ network ของ LibreChat>
EOF
grep '^OFFICE_DOCS_API_KEY=' office.env >> .env
```

| ค่า | ความหมาย |
|---|---|
| `OFFICE_PUBLIC_URL` | โดเมนที่ผู้ใช้เปิด ใช้สร้างลิงก์ดาวน์โหลด ต้องตรงทุกตัวอักษร (ไม่มี `/` ท้าย) |
| `OFFICE_FILE_TTL_HOURS` | ลบไฟล์ที่เก่ากว่านี้ทุกชั่วโมง = อายุของลิงก์ (ค่าเริ่มต้น 24) |
| `OFFICE_PREVIEW_IMAGES` | `true` = ส่งภาพกราฟ/แผนภาพ/หน้าแรก PDF ให้ AI ตรวจด้วย เปิดได้เฉพาะเมื่อ**ทุกโมเดล**ใน `modelSpecs` ดูรูปได้ ไม่อย่างนั้นโมเดลที่อ่านได้แค่ข้อความจะทำให้คำขอล้ม (ค่าเริ่มต้น `false`) |
| `LIBRECHAT_NETWORK` | network ของ LibreChat = `<ชื่อ compose project>_default` ดูด้วย `sudo docker network ls` หลังเปิด LibreChat |

**เปิดปิดชนิดไฟล์** — ใส่ใน `office.env` ค่า `on` หรือ `off` (ไม่ใส่ = `on`) ชนิดที่ปิดจะไม่ถูกส่งให้ AI เลย และ AI จะบอกผู้ใช้ว่าทำไม่ได้ โดยไม่ทำเป็นชนิดอื่นแทน
จึงลด token ทุกข้อความด้วย (PowerPoint ~4,900, Word ~1,600, Excel ~1,200 token)

| ค่า | ชนิดไฟล์ |
|---|---|
| `OFFICE_WORD` | Word (.docx) |
| `OFFICE_MEMO` | บันทึกข้อความ |
| `OFFICE_EXCEL` | Excel (.xlsx) |
| `OFFICE_POWERPOINT` | PowerPoint (.pptx) |
| `OFFICE_PDF` | PDF |
| `OFFICE_TXT` | ไฟล์ข้อความ .txt |
| `OFFICE_MD` | Markdown .md |
| `OFFICE_CSV` | ตาราง .csv |
| `OFFICE_JSON` | .json |
| `OFFICE_HTML` | หน้าเว็บ .html |
| `OFFICE_EMAIL` | ร่างอีเมล (.eml) |
| `OFFICE_XML` | XML |
| `OFFICE_CHART` | แผนภูมิ |
| `OFFICE_DIAGRAM` | แผนภาพ |
| `OFFICE_IMAGE` | สร้าง/แก้ภาพด้วย AI (`create_image`) ทำงานเมื่อมี `OFFICE_IMAGE_API_KEY` ด้วย |
| `OFFICE_ADMIN` | รายงานการใช้งาน + จัดการเครดิต ทำงานเมื่อมี `OFFICE_MONGO_URI` ด้วย |

**สร้างภาพ (ไม่บังคับ)** — `OFFICE_IMAGE_API_KEY` = คีย์ OpenRouter ตรง (`OFFICE_IMAGE_BASE_URL` ค่าเริ่มต้น `https://openrouter.ai/api/v1`)
ใช้ได้ทุกโมเดลภาพ; ผ่าน Portkey ได้เฉพาะโมเดล Gemini image (Portkey ไม่ส่งต่อ `/images` ของ OpenRouter) โดยตั้ง
`OFFICE_IMAGE_BASE_URL=https://api.portkey.ai/v1` และ `OFFICE_IMAGE_HEADERS={"x-portkey-config":"<config>"}`;
`OFFICE_IMAGE_MODELS` = รายชื่อโมเดลคั่นด้วย `,` ตัวแรกเป็นค่าเริ่มต้น

**เครื่องมือผู้ดูแล** — `OFFICE_MONGO_URI=mongodb://mongodb:27017/LibreChat` (อ่านรายงาน เขียนเฉพาะยอดเครดิต) และต้องมี entry
`office-admin` ใน `librechat.yaml` (ข้อ 5) ผู้ใช้ที่ role ไม่ใช่ `ADMIN` เรียกแล้วจะถูกปฏิเสธ

**วิธีที่ง่ายที่สุด (จากเครื่องตัวเอง):** แก้ค่า on/off ใน `office.env` ในเครื่อง แล้วรัน `./office/apply.sh` จากโฟลเดอร์ repo
(Git Bash บน Windows ได้) สคริปต์ตรวจตัวสะกด ส่งเฉพาะบรรทัด on/off ขึ้น server (สำรองไฟล์เดิม ไม่แตะรหัสผ่าน)
รีสตาร์ตให้ และแสดงผล ถ้าไม่มีอะไรเปลี่ยนจะไม่รีสตาร์ต ต้องใส่ที่อยู่ server ใน `office.env` ในเครื่องก่อน
(`OFFICE_REMOTE`, `OFFICE_REMOTE_KEY`, `OFFICE_REMOTE_DIR`, `OFFICE_REMOTE_COMPOSE` ดูหัวไฟล์ `office/apply.sh`)

ถ้าแก้บน server เอง ต้อง recreate ทั้ง office-files และ api ของ LibreChat (LibreChat อ่านรายการเครื่องมือครั้งเดียวตอนเริ่ม):

```bash
sudo docker compose -p aihub-office -f docker-compose.office.yml --env-file office.env up -d --force-recreate office-files
$COMPOSE up -d --force-recreate api
```

---

## 7. Reverse proxy และ HTTPS

ต้องมีสองเส้นทาง: `/office-docs/*` ไปที่ `office-docs:9000` และที่เหลือไป `api:3080`
**proxy ต้องส่ง Host header เดิมต่อไป** (office-docs ยังอัปโหลดผ่านโดเมนด้วยลายเซ็นที่ผูกกับโดเมน)

ลิงก์ดาวน์โหลดเป็นแบบสั้น `https://<โดเมน>/office-docs/<รหัสสุ่ม 16 ตัว>/<ชื่อไฟล์>` ไม่มีลายเซ็น:
bucket อนุญาตให้คนนอก **อ่าน** ไฟล์ตามชื่อเต็มเท่านั้น (ดูรายการ อัปโหลด หรือลบไม่ได้) office-files ตั้งค่านี้เองตอนเริ่ม

**Caddy** (`Caddyfile`, ตัวอย่างใช้ Let's Encrypt อัตโนมัติ):

```
<โดเมน> {
    handle /office-docs/* {
        reverse_proxy office-docs:9000
    }
    handle {
        reverse_proxy api:3080
    }
    encode gzip
    request_body {
        max_size 512MB
    }
}
```

ถ้าใช้ใบรับรองของลูกค้า เพิ่ม `tls /etc/caddy/certs/<cert>.crt /etc/caddy/certs/<cert>.key`
และ mount โฟลเดอร์ใบรับรองเข้า container ของ Caddy

Service ของ Caddy วางในไฟล์ compose ของ server (แบบ `docker-compose.lanna.yml` ของ server ทดสอบ):

```yaml
services:
  caddy:
    image: caddy:2-alpine
    restart: always
    depends_on: [api]
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./certs:/etc/caddy/certs:ro
      - caddy_data:/data
      - caddy_config:/config
volumes:
  caddy_data:
  caddy_config:
```

**nginx** (ถ้าลูกค้าใช้ nginx และอยู่ใน Docker network เดียวกัน):

```nginx
location /office-docs/ {
    proxy_pass http://office-docs:9000;
    proxy_set_header Host $host;
    client_max_body_size 50m;
}
location / {
    proxy_pass http://api:3080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_buffering off;
}
```

---

## 8. เปิดระบบ

```bash
cd /opt/librechat/<ชื่อ>
COMPOSE="sudo docker compose -p <ชื่อ project> -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.<ลูกค้า>.yml"

$COMPOSE up -d                                 # 1. LibreChat + proxy
sudo docker network ls                         # 2. ดูชื่อ network แล้วใส่ LIBRECHAT_NETWORK ใน office.env
sudo docker compose -p aihub-office -f docker-compose.office.yml --env-file office.env up -d --build   # 3. Office Files
$COMPOSE up -d --force-recreate api            # 4. ให้ LibreChat เชื่อม MCP ที่เพิ่งเปิด
```

---

## 9. ตรวจว่าใช้ได้

| ตรวจ | คำสั่ง | ผลที่ควรได้ |
|---|---|---|
| หน้า login | เปิด `https://<โดเมน>/login` | จอกว้างแบ่งครึ่ง (ซ้ายมีกล่องแชทตัวอย่างหมุนเวียน) จอแคบเป็นคอลัมน์เดียว ถ้าตั้ง SSO อย่างเดียวจะเหลือแค่ปุ่ม SSO |
| CSS รุ่นล่าสุด | `curl -s https://<โดเมน>/login \| grep -o 'space.css?v=[0-9]*'` | ตรงกับเลขใน `docker-compose.override.yml` |
| SSO | กดปุ่ม login | กลับมาที่หน้าแชทได้ |
| Office Files | `sudo docker ps --filter name=office` | 3 ตัว `healthy` + `office-net` |
| LibreChat เห็นเครื่องมือ | `sudo docker logs <api container> 2>&1 \| grep "MCP] Initialized"` | `1 configured server and 11 tools` (น้อยกว่านี้ถ้าปิดบางชนิดไฟล์ไว้) |
| สร้างไฟล์ได้จริง | ในแชทพิมพ์ "สร้างไฟล์ PDF สรุป 4P" | ได้ปุ่มดาวน์โหลด กดแล้วได้ไฟล์ |
| ลิงก์ปลอดภัย | `curl -s -o /dev/null -w "%{http_code}" https://<โดเมน>/office-docs/` | `403` (ดูรายการไฟล์ไม่ได้) |

---

## 10. ปัญหาที่เคยเจอ

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| หน้าเว็บยังเป็นแบบเก่าหลังอัปเดต | ใช้ `restart` แทน `up -d --force-recreate api` (`restart` ไม่ใส่ CSS ใหม่และไม่อ่าน `.env` ใหม่) |
| log ขึ้น `[MCP] Connection failed` และ office-docs log `invalid or missing API key` | `OFFICE_DOCS_API_KEY` ใน `.env` ไม่ตรงกับ `office.env` แก้ให้ตรงแล้ว `up -d --force-recreate` ทั้ง Office Files และ api |
| `Failed to inspect server ... OAuth Required: true` | Office Files รุ่นเก่าตอบ 401 ตอน LibreChat ตรวจ ใช้ `office/files/server.py` ล่าสุด |
| กดลิงก์แล้ว `AccessDenied` / `NoSuchKey` | ลิงก์หมดอายุ (ไฟล์ถูกลบหลัง `OFFICE_FILE_TTL_HOURS`) หรือ AI พิมพ์ลิงก์ผิด; ถ้าทุกลิงก์เปิดไม่ได้ ตรวจว่า office-files เริ่มได้ (มันตั้งสิทธิ์อ่านของ bucket ตอนเริ่ม) และ `OFFICE_PUBLIC_URL` ตรงกับโดเมน |
| สร้าง Word/Excel/PowerPoint แล้ว `Upload ... failed` | office-docs อัปโหลดผ่าน `OFFICE_PUBLIC_URL` ถ้า server เรียกโดเมนตัวเองไม่ได้ (NAT hairpin) เพิ่มใน service `office-net`: `extra_hosts: ["<โดเมน>:host-gateway"]` (ใบรับรองต้องถูกต้องสำหรับโดเมนนั้น) |
| Caddy reload แล้วขึ้น error หรือ Caddyfile มีแต่คำสั่ง | วางคำสั่งลงในไฟล์แทนเนื้อหา คืนจาก backup แล้ววางใหม่ ทดสอบด้วย `caddy validate` ก่อน `reload` |
| PowerPoint เปิดไฟล์ไม่ได้ | template รุ่นเก่า ใช้ `office/templates` ล่าสุด (สร้างจาก `office/build-templates.py`) |

---

## 11. ดูแลระบบ

**อัปเดตโค้ด**

```bash
git pull
node branding/build-space-css.js        # ถ้าแก้ CSS แล้วยังไม่ได้ build ใน commit
$COMPOSE up -d --force-recreate api
sudo docker compose -p aihub-office -f docker-compose.office.yml --env-file office.env up -d --build
```

**สำรองข้อมูล** — สิ่งที่ต้องสำรองคือ `data-node/` (MongoDB: ผู้ใช้, แชท), `uploads/`, `images/`, `.env`, `office.env`,
`librechat.yaml` ไฟล์ใน Office Files ไม่ต้องสำรอง (ลบเองหลัง `OFFICE_FILE_TTL_HOURS` ค่าเริ่มต้น 24 ชม.)

**เปลี่ยนคีย์ Office Files** — แก้ `OFFICE_DOCS_API_KEY` ทั้งใน `office.env` และ `.env` ให้ตรงกัน แล้ว recreate ทั้งสองชุด

**อัปเดตเวอร์ชัน office-docs / RustFS** — ล็อกไว้ใน `docker-compose.office.yml` ถ้าจะอัปเดต ทดสอบบนเครื่อง dev ก่อน
เพราะ `office/overlay/sitecustomize.py` อ้างโครงสร้างภายในของ office-docs (Python 3.12, `image_utils`, openpyxl, python-docx)

---

## 12. ปรับชื่อและหน้าตาให้ลูกค้า

ระบบนี้ใช้ชื่อ Lannacom AI Hub ถ้าลูกค้าต้องการชื่อหรือหน้าตาของตัวเอง เปลี่ยนที่:

| สิ่งที่เปลี่ยน | ที่ |
|---|---|
| ชื่อระบบ | `APP_TITLE` ใน `.env`, `<title>` ใน `command` ของ `docker-compose.override.yml`, `PRODUCT_NAME` ใน `branding/build-space-css.js`, `PRODUCT` ใน `branding/login.js` |
| โลโก้ ไอคอน | `branding/mark.svg` แล้วรัน `node branding/build-icons.js` (ดู `branding/README.md`) |
| หน้า login, สี, ฟอนต์, คำทักทาย | `branding/build-space-css.js` → `node branding/build-space-css.js` → เพิ่มเลข `space.css?v=`; หัวข้อและตัวอย่างแชทใน `branding/login.js` |
| สีในไฟล์ที่ AI สร้าง (ไม่มีโลโก้) | `INK`, `ACCENT`, `THEME_COLORS` ใน `office/build-templates.py` แล้วรันตามวิธีในหัวไฟล์; `COLORS` ใน `office/files/charts.py`; สีใน `office/files/diagrams.py`, `office/files/pdf.py`, `office/overlay/sitecustomize.py` (Excel); `office/templates/custom_email_template.html` |
| บันทึกข้อความ (`thai_memo`, ช่องตราสัญลักษณ์เว้นว่างไว้) | `build_memo()` ใน `office/build-templates.py` และ `office/config/docx_templates.yaml` |
| ฟอนต์ | `office/fonts/` (ต้องเป็นฟอนต์ที่อนุญาตให้ฝังและแจกต่อได้ เช่น OFL) |
