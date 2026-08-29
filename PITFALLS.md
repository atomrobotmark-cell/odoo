# 踩坑记录（软件开发 / 安装 / 调试全流程）

本文件汇总在 **WAHA 容器构建、Odoo 19 模块开发、安装部署、调试** 全过程踩过的所有坑。按阶段分类，每条给出 **现象 → 根因 → 解决方案**，便于日后复用与排错。

> 关联文档：[README.md](./README.md)（英文） / [README_zh.md](./README_zh.md)（中文）

---

## 〇、环境背景（决定了下面大部分坑）

- 目标机：**VM `192.168.140.175`**，运行 Docker Odoo 19 与 WAHA 容器，数据库 `atomrobot`。
- 网络现实：VM **直连外网被限速到 4–5 kB/s**（github / npm / deb.debian.org 直连都极慢，仅 HTTP 200 但吞吐崩溃）。
- 快路径：**Windows 上的 V2RayN 代理**（HTTP `10809` / SOCKS5 `10808`）。经代理 github 约 1.96 MB/s、npm 约 452 KB/s。
- WhatsApp 服务器（`graph` / `media.whatsapp.net`）VM 直连被墙（返回 000）；经代理 `graph.whatsapp.net` 返回 403 = 噪声握手主机可达 → **WAHA 运行期必须走代理连 WhatsApp**。

**反向隧道（把 Windows 代理暴露给 VM 内的 Docker）：**
| 隧道 | 用途 |
|---|---|
| `127.0.0.1:10809` → docker daemon | 拉基础镜像（daemon.json 注入 `HTTP_PROXY=127.0.0.1:10809`） |
| `192.168.140.175:10809` → build 容器 | 构建容器内下载（经 bridge 可达） |
| `10808` SOCKS5 → gows | whatsmeow 走 WhatsApp 原始 TLS |

> 设置隧道需要 sshd 开启 `GatewayPorts clientspecified` 且 `mark` 用户免密 sudo。

---

## 一、WAHA Docker 构建（waha-docker/）

| # | 现象 | 根因 | 解决方案 |
|---|---|---|---|
| 1 | 官方镜像直拉失败（1panel 对 466MB Chromium 层随机截断） | 大层在限速网络下不稳定 | **放弃直拉，改为 VM 源码构建 + GOWS 引擎**（Go 二进制，无 Chromium，约 2 GB vs 4 GB） |
| 2 | `apt-get update` 数小时 | `deb.debian.org` 在 GFW 后仅 5.4 kB/s | Dockerfile 把 18 处源改成 **TUNA 镜像**（`mirrors.tuna.tsinghua.edu.cn`）；实测经代理 36.7 MB/s、直连 47 MB/s（约快 6800 倍） |
| 3 | `npm` / `yarn` 报 `YN0035` 404 | **npmmirror（registry.npmmirror.com）缺包**，如 `@wppconnect/wa-version@1.5.4519` | 回滚用**官方 npm registry**（经代理可用，约 5 MB/s）；**绝不要用 npmmirror** |
| 4 | `libsignal` 原生模块构建失败（`YN0058`） | 需下载预编译二进制，受限环境失败；且 GOWS 根本不需要 | 从 `package.json` **删除 `libsignal`**；加 `ENV YARN_ENABLE_IMMUTABLE_INSTALLS=false` 允许更新 yarn.lock |
| 5 | `git clone` / submodule 在 build 容器内拉不到 | **git 不读 `HTTP_PROXY` 环境变量** | Dockerfile 在 `yarn install` 前执行 `git config http.proxy <proxy>` |
| 6 | `ffmpeg` / `opustags` 阶段卡死 | 只读聊天查看器不需要媒体转码；ffmpeg 是 deb.debian.org 慢路由下几百 MB 长 pole | **删除 ffmpeg + opustags**（libvips 保留，sharp 构建依赖） |
| 7 | 中国 Docker registry 镜像（USTC / 腾讯 / 163）全部不可达（返回 000） | 镜像站未收录 waha，或直连被墙 | **预构建镜像路线不通，只能源码构建** |
| 8 | Dockerfile 的 `golang` 阶段缺工具 | 后续步骤需要 wget 等 | 该阶段基础镜像改为 `node:24.11-bookworm-slim` 并补装 wget |

---

## 二、WAHA 运行期

| # | 现象 | 根因 | 解决方案 |
|---|---|---|---|
| 9 | 会话静默 FAILED，但 `/api/version` 仍显示 `gows` | **`WHATSAPP_DEFAULT_ENGINE` 必须大写**（`GOWS`）；源码用 `value in WAHAEngine`（枚举 KEY 大写）校验，小写 `gows` 静默回退 WEBJS | 用 `GOWS`（大写） |
| 10 | GOWS 会话起不来 / 连不上 WhatsApp | whatsmeow 走**原始 TCP**，不读 `HTTP_PROXY` 环境变量 | 建会话时显式传 `config.proxy.server`（见下） |
| 11 | 代理配置不生效 | `ProxyConfig.server` 只填 `host:port`，`getProxyUrl()` 会硬编码拼 `http://` | **不要带 `http://` 前缀**，写 `192.168.140.175:10809` |
| 12 | 容器重启后 API Key 变了，Odoo 配置失效 | 未固定 API Key | 固定 `WAHA_API_KEY=atomrobot-waha-local-2026`；Dashboard `admin` / `atomrobot-dash-2026` |
| 13 | 二维码扫一次就过期，会话变 FAILED | 二维码寿命约 1–2 分钟（WhatsApp Web 协议限制） | 过期后 `POST /api/sessions/default/start` 重新进入 `SCAN_QR_CODE` 取新码 |
| 14 | 取二维码接口报错 `0x89 invalid start byte` | `GET /api/:session/auth/qr` **直接返回 PNG 原始字节**，不是 base64 JSON | 按**二进制**解析，不要按 JSON / 文本解析 |
| 15 | 路由 404：`/api/sessions/:session/chats` | WAHA chat 路由是 **`/api/:session/...`**，不是 `/api/sessions/:session/...` | 全部改用 `/api/{session}/...`（如 `/api/default/chats`） |
| 16 | WAHA 文件端点（图片/视频/PDF）在浏览器 iframe 中 401 | 文件端点需要 `X-Api-Key` 请求头，`<img>` 标签无法带 header | 在 Odoo 建**代理路由** `/waha/file/<path>`，服务端补 API Key 转发 |
| 17 | 聊天历史只同步 1 条 | WhatsApp **关联设备固有限制**：新设备不同步完整历史，仅返回最近 1 条 + 新消息 | 非 bug；如需历史需主设备导出，产品层面告知用户 |
| 18 | Odoo → WAHA 请求走错代理 | daemon 注入了 `HTTP_PROXY`，Odoo 容器被带偏到 `127.0.0.1:10809` | Odoo 侧 requests 加 `proxies={'http':None,'https':None}` 强制**直连** `http://192.168.140.175:3000` |

---

## 三、Odoo 模块开发（whatsapp_waha_sender / export_doc_tracker）

| # | 现象 | 根因 | 解决方案 |
|---|---|---|---|
| 19 | 找不到 `res.partner.mobile` 字段 | **Odoo 19 已将 `mobile` 合并进 `phone`** | 全部改用 `phone` 字段（共 11 处：account / composer / mass_composer / controller 等） |
| 20 | `type='json'` 路由弃用警告 | Odoo 19 弃用 `@route(type='json')` | 改用 `type='jsonrpc'` |
| 21 | OwlError：`Cannot read properties of undefined (reading 'name')` | 自定义 OWL field widget `waha_chat_iframe` 与 Odoo 19 渲染管线不兼容 | 改用 `widget="html"` + computed `Html` 字段 `waha_chat_html`，HTML 中直接嵌 iframe |
| 22 | 打开联系人 WhatsApp Chat 标签页即报错；卸载模块后正常 | 旧模块 `waha_chat_viewer`（4/28 安装）与 `whatsapp_waha_sender` **都定义了 `waha.account` 模型**，`_partner_tree` 方法丢失 | **卸载旧模块**，只保留一个 |
| 23 | 点击 Sync 报 `Session expired` | `auth='user'` + iframe = 无会话 cookie | 改为 `auth='none'`，内部操作用 `.sudo()` |
| 24 | 点击 Sync 报 `Error: unknown` / `[object Object]` | JS 未解包 jsonrpc 响应格式 `{jsonrpc, id, result:{...}}`，`d.ok` 为 undefined | JS 先取 `raw.result` 再访问 `d.result.ok` / `d.result.count` |
| 25 | 图片 / 视频 / PDF 不显示 | 同 #16，WAHA 文件端点需 `X-Api-Key` | 新增 Odoo 代理路由 `/waha/file/<session>/<path>` 服务端转发 |
| 26 | `media_type` 始终为空 | WAHA 把 MIME 放在 `media.mimetype`，而非顶层 `type` | 读取 `media.mimetype` 推断类型（image / video / audio / document） |
| 27 | `media_url` 未保存，媒体无法渲染 | `upsert_from_waha` 没写 `media_url` 字段 | 提取 `media.url`，并把 `localhost:3000` **替换为真实 WAHA 主机地址** |

---

## 四、Odoo 模块安装与部署（Docker）

| # | 现象 | 根因 | 解决方案 |
|---|---|---|---|
| 28 | 模块不生效 / 找不到 | 放错 addons 路径 | Docker Odoo 模块路径：`/var/lib/docker/volumes/odoo-data/_data/.local/share/Odoo/addons/19.0/`（容器内 `/var/lib/odoo/.local/share/Odoo/addons/19.0/`） |
| 29 | 改了代码不生效 | Python 缓存 / 模块未更新 | 部署后清缓存：`sudo find <module_path> -name __pycache__ -type d -exec rm -rf {} +`；再 `docker exec odoo odoo -u <module> -d <db> --stop-after-init` |
| 30 | 文件权限 / 属主异常 | 容器内 addons 属主是 `dhcpcd:netdev` | 用 `sudo cp -a` 并保持 `sudo chown -R dhcpcd:netdev` |
| 31 | 模块状态不明 | —— | 查状态：`docker exec odoo-db psql -U odoo -d <db> -tAc "select name,state from ir_module_module where name like '%waha%';"` |
| 32 | 装模块后必须重启 | —— | `docker restart odoo` |

---

## 五、Git / SSH 操作

| # | 现象 | 根因 | 解决方案 |
|---|---|---|---|
| 33 | `pkill -f "docker build"` 把自己命令行也杀了 | 该模式匹配到执行命令自身 | 用 `pkill -9 -x docker` 或**按 PID 精确杀** |
| 34 | `ssh 'sudo ... psql -c "select ... where ..."'` 引号嵌套地狱 | 单引号里再嵌单引号 | 用 **`ssh < script.sh`** 管道传 SQL 脚本文件，避免嵌套引号 |
| 35 | 明文 GitHub token 泄露风险 | 用户曾把 `ghp_...` 明文贴进对话 | **绝不写入文件**；用完立即去 GitHub 后台删除；本仓库全程用 **SSH key（ed25519）** 推送 |
| 36 | CRLF / LF 警告 | Windows Git 默认 CRLF | 无害，可加 `.gitattributes` 统一，非阻塞 |

---

## 六、通用调试经验

1. **先确认连通性再谈功能**：用 `GET /api/version` 探活 WAHA；用 `GET /api/:session/chats` 验证能否拉到真实聊天，再排查模块。
2. **静默失败最危险**：WAHA 引擎小写回退、GOWS 不读 `HTTP_PROXY` 都是"看起来配了但没生效"，务必用日志 / 状态接口确认 `connected: true`、`SCAN_QR_CODE` / `WORKING`。
3. **区分"运行期代理"与"构建期代理"**：daemon 注入的代理、容器 env 的代理、whatsmeow 的 proxy.server、git/npm 的代理是**四套独立机制**，互相不继承。
4. **端到端验证清单**：Odoo 模块 installed 无告警 → Odoo 建 WAHA 账户（base_url / session / API Key）→ `_get('chats')` 拉到真实聊天 → 前端 iframe 渲染 → 真实扫码登录 → 收消息。
5. **扫码手机号格式**：WAHA 返回 `8615510979062@c.us`，匹配联系人用去掉 `@c.us` 的 `8615510979062` 或 `+86 155 1097 9062`。

---

## 七、一键 checklist（新环境部署前自查）

- [ ] Dockerfile 已切 TUNA apt 镜像（非 deb.debian.org）
- [ ] npm 用官方源（非 npmmirror），且经代理可达
- [ ] `package.json` 已删 `libsignal`
- [ ] `WHATSAPP_DEFAULT_ENGINE=GOWS`（大写）
- [ ] 建会话传 `config.proxy.server`（host:port，无 http://）
- [ ] `WAHA_API_KEY` 固定
- [ ] Odoo 模块：无 `res.partner.mobile`、路由 `type='jsonrpc'`、无旧 `waha_chat_viewer` 冲突
- [ ] Odoo 侧请求 WAHA 用 `proxies={'http':None,'https':None}` 直连
- [ ] 媒体显示走 Odoo `/waha/file/` 代理
- [ ] 推送用 SSH key，明文 token 已删除

---

*整理时间：2026-08-29 · 适用版本：Odoo 19.0 / WAHA GOWS 引擎 / Docker*
