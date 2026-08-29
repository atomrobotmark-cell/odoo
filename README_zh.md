# Odoo 19 自定义模块 + WAHA Docker 构建（中文说明）

本仓库包含为 Odoo 19 社区版开发的自定义模块及 Docker 构建配置，由 ATOMROBOT（天津辰星技术股份有限公司）开发。

> English version: [README.md](./README.md) · 踩坑记录：[PITFALLS.md](./PITFALLS.md)

## 仓库结构

```
├── export_doc_tracker/          # Odoo 模块：出口单据追踪
├── whatsapp_waha_sender/        # Odoo 模块：基于 WAHA 的 WhatsApp 集成
└── waha-docker/                 # WAHA Docker 镜像构建文件
    ├── Dockerfile               # 自定义 WAHA 构建（GOWS 引擎，无 Chromium）
    ├── package.json             # WAHA 依赖
    ├── waha.config.json         # WAHA 配置（仪表盘版本）
    └── waha_run.sh              # 启动脚本
```

---

## 1. export_doc_tracker（出口单据追踪）

用于国际贸易的出口单据追踪与管理。在销售订单（Sales Order）上新增"出口单据（Export Documents）"标签页。

### 功能

- 交单方式（L/C 信用证、T/T 电汇、D/P 付款交单、D/A 承兑交单）
- 制单阶段跟踪（未开始 Not Started → 制单中 Preparing → 已就绪 Ready → 已交单 Submitted）
- 一键"标记已交单（Mark as Submitted）"
- 4 种报表模板：
  - **商业发票 Commercial Invoice** — `/report/pdf/export_doc_tracker.report_commercial_invoice/<sale_order_id>`
  - **装箱单 Packing List** — `/report/pdf/export_doc_tracker.report_packing_list/<sale_order_id>`
  - **报关草单 Customs Draft** — `/report/pdf/export_doc_tracker.report_customs_draft/<sale_order_id>`
  - **唛头 Shipping Mark** — `/report/html/export_doc_tracker.report_shipping_mark/<sale_order_id>`
- 唛头自动生成（项目代码 + 随机 6 位数字编号）
- 发票号自动从关联发票中带出

### 依赖模块

`sale`、`sale_stock`、`stock`、`account`

### 安装

```bash
# 基于 Docker 的 Odoo：
docker cp export_doc_tracker odoo:/var/lib/odoo/.local/share/Odoo/addons/19.0/
docker exec odoo odoo -i export_doc_tracker -d <your_db> --stop-after-init
docker restart odoo

# 修改后更新：
docker exec odoo odoo -u export_doc_tracker -d <your_db> --stop-after-init
docker restart odoo
```

---

## 2. whatsapp_waha_sender（基于 WAHA 的 WhatsApp 集成）

通过 [WAHA](https://github.com/devlikeapro/waha)（WhatsApp HTTP API）实现的 WhatsApp 集成。在 Odoo 内提供只读聊天查看器，并支持消息同步与发送。

### 功能

- **聊天查看器（Chat Viewer）** — 在联系人 / CRM / 销售 / 发票表单中内嵌 iframe，展示 WhatsApp 历史消息
- **消息同步（Message Sync）** — 从 WAHA 拉取消息并缓存到 Odoo（`waha.chat.message` 模型）
- **发送消息（Send Messages）** — 通过 WAHA API 从 Odoo 发送 WhatsApp 消息
- **批量发送（Bulk Composer）** — 一次向多个联系人发送
- **媒体代理（Media Proxy）** — 图片、视频、PDF 经 `/waha/file/...` 代理路由直接内联显示
- **多账号（Multi-Account）** — 支持多个 WAHA 实例

### 依赖模块

`base`、`mail`、`crm`、`sale`、`account`

### 安装

```bash
# 基于 Docker 的 Odoo：
docker cp whatsapp_waha_sender odoo:/var/lib/odoo/.local/share/Odoo/addons/19.0/
docker exec odoo odoo -i whatsapp_waha_sender -d <your_db> --stop-after-init
docker restart odoo
```

### 配置

1. 进入 **WhatsApp → WAHA 账号（WAHA Accounts）**
2. 新建一个账号：
   - **名称（Name）**：例如 `WAHA Local (GOWS)`
   - **基础地址（Base URL）**：`http://<waha_host>:3000`
   - **API Key**：你的 WAHA API Key
   - **会话（Session）**：`default`
3. 点击 **测试连接（Test Connection）** 验证

---

## 3. WAHA Docker 构建（waha-docker/）

为 WAHA 定制的 Docker 构建，采用 **GOWS 引擎**（基于 Go 的 WhatsApp Web 实现，无需 Chromium）。相比完整 WAHA 镜像显著更轻量（约 2 GB vs 约 4 GB）。

### 为什么从源码构建？

官方 WAHA 镜像包含供 WEBJS 引擎使用的 Chromium，而我们用不到。仅用 GOWS 构建可节省约 2 GB 磁盘空间，并规避 Chromium 相关的各种问题。

### 前置条件

- 已安装 Docker
- 可访问互联网（或代理——见下方代理章节）
- WAHA 源码（从 https://github.com/devlikeapro/waha 克隆）

### 构建

```bash
# 克隆 WAHA 源码
git clone https://github.com/devlikeapro/waha.git waha-src
cd waha-src

# 复制我们定制的 Dockerfile（替换原始文件）
cp <path-to>/waha-docker/Dockerfile .

# 使用 GOWS 引擎构建（无 Chromium）
docker build \
  --build-arg USE_BROWSER=none \
  --build-arg WHATSAPP_DEFAULT_ENGINE=gows \
  -t waha-gows:local .
```

### 使用代理构建（中国 / 防火墙环境）

如果你在中国或处于防火墙之后，默认的 Debian / npm 镜像速度极慢。我们的 Dockerfile 已将 apt 改为使用 **清华大学 TUNA 镜像**（快约 6800 倍）。对于 npm 和 git，请传入代理构建参数：

```bash
docker build \
  --build-arg HTTP_PROXY=http://<proxy_host>:<proxy_port> \
  --build-arg HTTPS_PROXY=http://<proxy_host>:<proxy_port> \
  --build-arg USE_BROWSER=none \
  --build-arg WHATSAPP_DEFAULT_ENGINE=gows \
  -t waha-gows:local .
```

**⚠️ 不要使用国内 npm 镜像（npmmirror）** —— 它们缺少 `@wppconnect/wa-version` 等包，会导致 Yarn 报 404 错误。请通过代理使用官方 npm 源。

### 运行

```bash
# 使用提供的脚本：
chmod +x waha_run.sh
./waha_run.sh

# 或手动运行：
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

### 使用代理创建会话

GOWS（whatsmeow）会以原始 TCP 方式连接 WhatsApp 服务器，**不会读取** `HTTP_PROXY` 环境变量。你**必须**在会话中配置代理：

```bash
# 创建带代理的会话
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

**⚠️ 代理的 server 字段只能是 `host:port` 格式——不要加 `http://` 前缀。**

### 登录（二维码）

1. 在手机上打开 WhatsApp
2. 进入 **设置 → 关联设备 → 关联设备（Link a Device）**
3. 获取二维码：`curl http://localhost:3000/api/default/auth/qr -H "X-Api-Key: <key>"`（返回原始 PNG 字节）
4. 用手机扫码
5. 会话状态应变为 `WORKING`

---

## 已知问题与踩坑记录

### WAHA / Docker

| 问题 | 原因 | 解决方案 |
|---|---|---|
| **构建极其缓慢（数小时）** | 防火墙后 `deb.debian.org` 被限速 | 修改 Dockerfile 使用 `mirrors.tuna.tsinghua.edu.cn`（已完成） |
| **npm 404 错误** | 国内 npm 镜像（npmmirror）缺少部分包 | 通过代理使用官方 npm 源，不要用 npmmirror |
| **`libsignal` 构建失败** | 原生模块需要预编译二进制，受限环境编译失败 | 从 `package.json` 移除 `libsignal`（GOWS 引擎不需要） |
| **`WHATSAPP_DEFAULT_ENGINE` 必须大写** | WAHA 用 `value in WAHAEngine`（枚举键为大写）校验 | 使用 `GOWS`，不要写 `gows`（小写会静默回退到 WEBJS） |
| **GOWS 会话不加代理配置就会失败** | whatsmeow 走原始 TCP，忽略 `HTTP_PROXY` | 在创建会话时传 `config.proxy.server`（仅 host:port） |
| **二维码约 20 秒过期** | WhatsApp Web 协议限制 | 快速重新生成：`POST /api/sessions/default/stop` 再 `start` |
| **WAHA 二维码接口返回原始 PNG** | 并非某些文档所说 base64 JSON | 按二进制解析，不要按 JSON 处理 |
| **国内 Docker 镜像仓库不可达** | USTC / 腾讯 / 163 镜像返回 000 | 必须源码构建，无法拉取预构建镜像 |

### Odoo 模块（whatsapp_waha_sender）

| 问题 | 原因 | 解决方案 |
|---|---|---|
| **找不到 `res.partner.mobile` 字段** | Odoo 19 已将 `mobile` 合并进 `phone` | 只用 `phone` 字段 |
| **`type='json'` 弃用警告** | Odoo 19 弃用了 `type='json'` | 改用 `type='jsonrpc'` |
| **两个 WhatsApp 模块冲突** | `waha_chat_viewer` 与 `whatsapp_waha_sender` 都定义了 `waha.account` | 卸载旧模块，只保留一个 |
| **OWL 报错 `Cannot read properties of undefined (reading 'name')`** | 自定义 OWL 字段 widget 与 Odoo 19 渲染管线不兼容 | 改用 `widget="html"` + 计算型 `Html` 字段，替代自定义 widget |
| **同步按钮报 `Error: unknown`** | JS 未解包 jsonrpc 响应（`{jsonrpc, id, result}`） | 在判断 `d.ok` 前先取 `raw.result` |
| **iframe 内提示 `Session expired`** | `auth='user'` + iframe = 无会话 cookie | 内部操作用 `auth='none'` + `.sudo()` |
| **图片 / 视频不显示** | WAHA 文件端点需要 `X-Api-Key` 请求头；`<img>` 标签无法带请求头 | 在 Odoo 建代理路由 `/waha/file/...`，由服务端补上 API Key |
| **媒体 URL 使用 `localhost:3000`** | WAHA 返回的是内部地址 | 同步时把 `localhost:3000` 替换为真实的 WAHA 主机地址 |
| **`media_type` 始终为空** | WAHA 把 MIME 类型放在 `media.mimetype`，而非顶层 `type` | 读取 `media.mimetype` 并推断类型（image / video / audio / document） |

### 部署提示

- **Docker Odoo 上模块文件位置**：`/var/lib/docker/volumes/odoo-data/_data/.local/share/Odoo/addons/19.0/`
- **文件属主**：`dhcpcd:netdev` —— 始终用 `sudo cp -a` 并 `sudo chown` 保留
- **部署后清理 Python 缓存**：`sudo find <module_path> -name __pycache__ -type d -exec rm -rf {} +`
- **强制更新模块**：`sudo docker exec odoo odoo -u <module_name> -d <db> --stop-after-init`
- **查看模块状态**：`sudo docker exec odoo-db psql -U odoo -d <db> -tAc "select name,state from ir_module_module where name like '%waha%';"`

---

## 许可证

LGPL-3.0
