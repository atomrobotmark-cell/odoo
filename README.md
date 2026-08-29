# Odoo 19 Custom Modules + WAHA Docker Build

Custom modules and Docker build configuration for Odoo 19 Community, developed for ATOMROBOT (Tianjin Chenxing Technology Co., Ltd.).

> 中文说明：[README_zh.md](./README_zh.md)

## Repository Structure

```
├── export_doc_tracker/          # Odoo module: Export document tracking
├── whatsapp_waha_sender/        # Odoo module: WhatsApp integration via WAHA
└── waha-docker/                 # WAHA Docker image build files
    ├── Dockerfile               # Custom WAHA build (GOWS engine, no Chromium)
    ├── package.json             # WAHA dependencies
    ├── waha.config.json         # WAHA config (dashboard version)
    └── waha_run.sh              # Launch script
```

---

## 1. export_doc_tracker

Export document tracking and management for international trade. Adds an "Export Documents" tab on Sales Orders.

### Features

- Document submission method (L/C, T/T, D/P, D/A)
- Document preparation stage tracking (Not Started → Preparing → Ready → Submitted)
- One-click "Mark as Submitted"
- 4 report templates:
  - **Commercial Invoice** — `/report/pdf/export_doc_tracker.report_commercial_invoice/<sale_order_id>`
  - **Packing List** — `/report/pdf/export_doc_tracker.report_packing_list/<sale_order_id>`
  - **Customs Draft** (报关草单) — `/report/pdf/export_doc_tracker.report_customs_draft/<sale_order_id>`
  - **Shipping Mark** (唛头) — `/report/html/export_doc_tracker.report_shipping_mark/<sale_order_id>`
- Shipping mark auto-generation with project code + random 6-digit ID
- Invoice number pulled from linked invoices

### Dependencies

`sale`, `sale_stock`, `stock`, `account`

### Installation

```bash
# Docker-based Odoo:
docker cp export_doc_tracker odoo:/var/lib/odoo/.local/share/Odoo/addons/19.0/
docker exec odoo odoo -i export_doc_tracker -d <your_db> --stop-after-init
docker restart odoo

# Update after changes:
docker exec odoo odoo -u export_doc_tracker -d <your_db> --stop-after-init
docker restart odoo
```

---

## 2. whatsapp_waha_sender

WhatsApp integration via [WAHA](https://github.com/devlikeapro/waha) (WhatsApp HTTP API). Provides a read-only chat viewer inside Odoo with message sync and send capabilities.

### Features

- **Chat Viewer** — Embedded iframe in contact/CRM/Sales/Invoice forms showing WhatsApp history
- **Message Sync** — Pull messages from WAHA into Odoo cache (`waha.chat.message`)
- **Send Messages** — Send WhatsApp messages from Odoo via WAHA API
- **Bulk Composer** — Send to multiple contacts at once
- **Media Proxy** — Images, videos, PDFs displayed inline via `/waha/file/...` proxy route
- **Multi-Account** — Support multiple WAHA instances

### Dependencies

`base`, `mail`, `crm`, `sale`, `account`

### Installation

```bash
# Docker-based Odoo:
docker cp whatsapp_waha_sender odoo:/var/lib/odoo/.local/share/Odoo/addons/19.0/
docker exec odoo odoo -i whatsapp_waha_sender -d <your_db> --stop-after-init
docker restart odoo
```

### Configuration

1. Go to **WhatsApp → WAHA Accounts**
2. Create a new account:
   - **Name**: e.g. `WAHA Local (GOWS)`
   - **Base URL**: `http://<waha_host>:3000`
   - **API Key**: your WAHA API key
   - **Session**: `default`
3. Click **Test Connection** to verify

---

## 3. WAHA Docker Build (waha-docker/)

Custom Docker build for WAHA using the **GOWS engine** (Go-based WhatsApp Web, no Chromium required). This is significantly lighter than the full WAHA image (~2 GB vs ~4 GB).

### Why Build from Source?

The official WAHA image includes Chromium for the WEBJS engine, which we don't need. Building with GOWS only saves ~2 GB of disk space and avoids Chromium-related issues.

### Prerequisites

- Docker installed
- Internet access (or proxy — see proxy section below)
- WAHA source code (cloned from https://github.com/devlikeapro/waha)

### Build

```bash
# Clone WAHA source
git clone https://github.com/devlikeapro/waha.git waha-src
cd waha-src

# Copy our custom Dockerfile (replaces the original)
cp <path-to>/waha-docker/Dockerfile .

# Build with GOWS engine (no Chromium)
docker build \
  --build-arg USE_BROWSER=none \
  --build-arg WHATSAPP_DEFAULT_ENGINE=gows \
  -t waha-gows:local .
```

### Build with Proxy (China / Behind Firewall)

If you're in China or behind a firewall, the default Debian/npm mirrors are extremely slow. Our Dockerfile patches apt to use **Tsinghua TUNA mirror** (6800× faster). For npm and git, pass proxy build args:

```bash
docker build \
  --build-arg HTTP_PROXY=http://<proxy_host>:<proxy_port> \
  --build-arg HTTPS_PROXY=http://<proxy_host>:<proxy_port> \
  --build-arg USE_BROWSER=none \
  --build-arg WHATSAPP_DEFAULT_ENGINE=gows \
  -t waha-gows:local .
```

**⚠️ Do NOT use China npm mirrors (npmmirror)** — they are missing packages like `@wppconnect/wa-version`, causing Yarn to fail with 404 errors. Use the official npm registry via proxy instead.

### Run

```bash
# Using the provided script:
chmod +x waha_run.sh
./waha_run.sh

# Or manually:
docker rm -f waha 2>/dev/null
docker run -d --name waha --restart unless-stopped -p 3000:3000 \
  -e WHATSAPP_DEFAULT_ENGINE=GOWS \
  -e WAHA_API_KEY=<your_api_key> \
  -e WAHA_DASHBOARD_USERNAME=admin \
  -e WAHA_DASHBOARD_PASSWORD=<your_password> \
  -e HTTP_PROXY=http://<proxy_host>:<proxy_port> \
  -e HTTPS_PROXY=http://<proxy_host>:<proxy_port> \
  -e NO_PROXY=localhost,127.0.0.1 \
  waha-gows:local
```

### Create Session with Proxy

GOWS (whatsmeow) makes raw TCP connections to WhatsApp servers and does **not** read `HTTP_PROXY` environment variables. You **must** configure the proxy in the session:

```bash
# Create session with proxy
curl -X POST http://localhost:3000/api/sessions/ \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: <your_api_key>" \
  -d '{
    "name": "default",
    "start": true,
    "config": {
      "proxy": {
        "server": "<proxy_host>:<proxy_port>"
      }
    }
  }'
```

**⚠️ The proxy server field must be `host:port` only — do NOT include `http://` prefix.**

### Login (QR Code)

1. Open WhatsApp on your phone
2. Go to **Settings → Linked Devices → Link a Device**
3. Fetch the QR code: `curl http://localhost:3000/api/default/auth/qr -H "X-Api-Key: <key>"` (returns raw PNG bytes)
4. Scan with your phone
5. Session status should change to `WORKING`

---

## Known Issues & Pitfalls

### WAHA / Docker

| Issue | Cause | Solution |
|---|---|---|
| **Extremely slow build** (hours) | `deb.debian.org` is throttled behind GFW | Patch Dockerfile to use `mirrors.tuna.tsinghua.edu.cn` (already done) |
| **npm 404 errors** | China npm mirrors (npmmirror) are missing packages | Use official npm registry via proxy, not npmmirror |
| **`libsignal` build failure** | Native module needs prebuilt binaries, fails in restricted environments | Remove `libsignal` from `package.json` (not needed for GOWS engine) |
| **`WHATSAPP_DEFAULT_ENGINE` must be UPPERCASE** | WAHA validates with `value in WAHAEngine` (enum keys are uppercase) | Use `GOWS`, not `gows` (lowercase silently falls back to WEBJS) |
| **GOWS session FAILS without proxy config** | whatsmeow makes raw TCP connections, ignores `HTTP_PROXY` | Pass `config.proxy.server` in session creation (host:port only) |
| **QR code expires in ~20 seconds** | WhatsApp Web protocol limitation | Regenerate quickly: `POST /api/sessions/default/stop` then `start` |
| **WAHA QR endpoint returns raw PNG** | Not base64 JSON as some docs suggest | Parse as binary, not JSON |
| **China Docker registry mirrors unreachable** | USTC/Tencent/163 mirrors return 000 | Must build from source, cannot pull pre-built image |

### Odoo Module (whatsapp_waha_sender)

| Issue | Cause | Solution |
|---|---|---|
| **`res.partner.mobile` field not found** | Odoo 19 merged `mobile` into `phone` | Use `phone` field only |
| **`type='json'` deprecation warning** | Odoo 19 deprecated `type='json'` | Use `type='jsonrpc'` instead |
| **Two WhatsApp modules conflict** | `waha_chat_viewer` and `whatsapp_waha_sender` both define `waha.account` | Uninstall the old module, keep only one |
| **OWL `Cannot read properties of undefined (reading 'name')`** | Custom OWL field widget incompatible with Odoo 19 rendering pipeline | Use `widget="html"` with computed `Html` field instead of custom widget |
| **Sync button `Error: unknown`** | JS didn't unwrap jsonrpc response (`{jsonrpc, id, result}`) | Access `raw.result` before checking `d.ok` |
| **Sync `Session expired` in iframe** | `auth='user'` + iframe = no session cookie | Use `auth='none'` + `.sudo()` for internal operations |
| **Images/videos not displaying** | WAHA file endpoint requires `X-Api-Key` header; `<img>` tags can't send headers | Build Odoo proxy route `/waha/file/...` that adds the API key server-side |
| **Media URLs use `localhost:3000`** | WAHA returns internal URLs | Replace `localhost:3000` with actual WAHA host address during sync |
| **`media_type` always empty** | WAHA puts mimetype in `media.mimetype`, not top-level `type` | Read `media.mimetype` and infer type (image/video/audio/document) |

### Deployment Tips

- **Module files location on Docker Odoo**: `/var/lib/docker/volumes/odoo-data/_data/.local/share/Odoo/addons/19.0/`
- **File ownership**: `dhcpcd:netdev` — always preserve with `sudo cp -a` and `sudo chown`
- **Clear Python cache after deploying**: `sudo find <module_path> -name __pycache__ -type d -exec rm -rf {} +`
- **Force update module**: `sudo docker exec odoo odoo -u <module_name> -d <db> --stop-after-init`
- **Check module state**: `sudo docker exec odoo-db psql -U odoo -d <db> -tAc "select name,state from ir_module_module where name like '%waha%';"`

---

## License

LGPL-3.0
