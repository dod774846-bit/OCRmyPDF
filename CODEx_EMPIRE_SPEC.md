# Codex 帝国根基说明书（Windows 桌面端 Python 商业体系）
你是我的工程代理（Codex）。你的任务是：在任何新产品（第2/第3/第100款）里，统一复用并升级同一套“商业闭环体系”。
我只会提供：产品名称、产品功能描述、以及一个待改造的 GitHub 项目（或基础模板仓库）。
你必须独立完成：集成商业闭环、写测试、跑测试、打包自检、输出可交付的打包命令与产物验证步骤。

---

## 0. 产品信息（我会填写）
- 产品名称：<PRODUCT_NAME>
- 产品一句话定位：<ONE_LINE_PITCH>
- 目标人群：<TARGET_AUDIENCE>
- 核心功能（MVP）：<MVP_FEATURES>
- 付费点（权益定义）：<PAYWALL_RULES>
- 产品ID（唯一）：<PRODUCT_ID>  （例如 "p_bg_remove_pro"）
- 版本号：<SEMVER>  （例如 "1.0.0"）

---

## 1. 技术约束与环境
- 平台：Windows 10/11
- 语言：Python 3.10+（如现有项目不同，你负责升级/适配）
- GUI：优先 PyQt6（如果原项目是 Tkinter / wx / etc.，保留框架但必须提供同等支付墙/更新提示能力）
- 打包：PyInstaller（单文件或文件夹模式都行，优先“稳定可打包”）
- 开发环境：VSCode
- 网络：产品可强联网或弱联网，默认强联网（见授权策略）
- GPU：若涉及 CUDA/torch 等，必须提供 CPU fallback + 打包可行性自检

---

## 2. 目标：统一“商业闭环底座”能力（必须全部具备）
你必须在新产品中实现/复用以下能力（可来自旧代码，但要整理成可复用模块）：

### 2.1 云端配置（动态可控）
- 客服信息、公告、广告文案、价格、套餐、下载链接、最新版本号、活动开关等，必须可由服务端动态下发
- 客户端必须缓存云配置（TTL），并提供离线降级默认值

### 2.2 强制更新（防旧版绕过）
- 客户端启动时拉取云配置，若发现 `latest_version > current_version` 且 `force_update=true`，必须阻止继续使用，并引导下载
- 允许灰度：按版本范围/渠道/产品ID控制

### 2.3 授权与防白嫖（核心）
- 客户端必须具备设备指纹 device_id（稳定、可重复、尽量不易伪造）
- 许可 key（license_key）需本地持久化（加密或签名校验，至少避免明文可随意改）
- 客户端每次使用核心功能前必须经过授权策略闸门（见 2.4）

### 2.4 授权策略（可配置，默认强联网）
实现三种策略，服务端通过云配置下发：
- STRICT_ONLINE：每次关键动作前都向服务端校验 + 扣量；断网即不可用
- GRACE_PERIOD：允许离线 N 小时（本地保存签名票据），到期必须联网刷新
- OFFLINE_PRO：买断/企业版允许离线长期使用（基于设备证书 + 签名授权）

### 2.5 计费与订单（收钱闭环）
- 客户端可以创建订单（带 product_id、device_id、order_type）
- 客户端展示二维码/支付链接（UI 支付墙对话框必须存在）
- 客户端轮询订单状态（间隔可配）
- 支付成功后自动激活（更新 license_key 或权益状态）
- 订单要去重：N 分钟内同 device_id+product_id+order_type 复用同一订单

### 2.6 扣量/配额（按次/按日/按月都能扩展）
- trial 用户：默认每日免费次数（例如 3 次），服务端按 device_id+product_id+date 记录
- 付费用户：根据套餐决定（无限/每日上限/月上限/有效期）
- 客户端必须在实际完成一次“可计费动作”后上报 usage（避免只点按钮就扣）

### 2.7 反滥用与安全最低线（必须做到）
- 服务端所有密钥/密码/Token 必须来自环境变量（.env），不得硬编码进源码
- 服务端接口必须至少具备一种防刷机制：
  - 请求签名（推荐）或
  - server-issued token + 时间戳 + nonce 或
  - 简单速率限制（最低线）
- 日志不得打印：任何密钥、完整 license_key、支付回调敏感字段

---

## 3. 代码交付形态：帝国标准目录（你必须按此整理）
你需要把“商业底座”整理成一个可复制的模板结构；新产品只替换业务逻辑与 UI 文案。

建议目录（可微调，但模块边界必须清晰）：

/app
  /ui
    main_window.py
    paywall_dialog.py        # 统一支付墙组件（可复用）
    update_dialog.py         # 统一强制更新弹窗
  /core
    business_action.py       # 产品核心功能封装（计费动作在这里触发）
  /empire
    client.py                # EmpireClient：所有 HTTP API 封装、重试、超时、错误码
    auth.py                  # 授权策略、票据缓存、license 读写（加密/签名）
    device.py                # device_id 生成
    config.py                # 云配置拉取与缓存
    usage.py                 # usage 上报与扣量封装
    errors.py                # 统一异常
  main.py                    # 启动入口：拉配置->检查更新->初始化授权->启动 UI

/server
  main.py                    # FastAPI 入口
  /routes
    config.py
    billing.py               # create_order, check_order, notify/callback
    license.py               # check_license
    usage.py                 # report_usage
  /services
    pocketbase_repo.py       # 数据层（PocketBase）
    billing_service.py
    license_service.py
    security.py              # 签名/验签、速率限制
  .env.example               # 所需环境变量模板（不含真实值）

/tests
  test_empire_client.py
  test_license_flow.py
  test_usage_quota.py
  test_update_policy.py
  test_packaging_smoke.py    # 打包后冒烟测试（见第8节）

/scripts
  run_tests.ps1
  build.ps1
  smoke_test.ps1
  apply_patch.ps1            # 离线补丁应用脚本（方案A要求）

---

## 4. 数据库契约（PocketBase collections，必须兼容现有结构）
服务端必须使用 PocketBase，并且与以下 collections/字段保持一致（允许新增字段，但禁止破坏/重命名已有字段）。
当前结构覆盖：产品、订单、license、设备绑定、用量、监控、日志等闭环。

### 4.1 products（产品与云配置/价格/更新/广告）
- collection: `products`
- 字段（至少要支持映射）：
  - name: text
  - status: select {active, maintenance, deprecated}
  - product_id: text（业务唯一ID，例如 p_xxx）
  - free_quota_per_day: number
  - latest_version: text
  - config_version: number（用于客户端缓存失效/热更新）
  - download_url: url
  - cdn_url_cn: url
  - cdn_url_global: url
  - ad_text: text
  - ad_image_url: url
  - ad_target_url: url
  - ad_link: url
  - qq_support: text
  - buy_link: url
  - price_monthly: number
  - price_yearly: number
  - price_lifetime: number
要求：服务端 `/config` 返回字段必须可由该表生成。

### 4.2 devices（设备表）
- collection: `devices`
- 字段：
  - machine_code: text（客户端 device_id 或其派生/指纹）
  - risk_level: select {safe, suspicious, banned}
  - first_seen_at: date
  - last_seen_at: date
要求：check_license / create_order / report_usage 时 upsert 并更新 last_seen。

### 4.3 licenses（授权码/套餐）
- collection: `licenses`
- 字段：
  - key: text（license_key）
  - product_id: relation -> products
  - type: select {lifetime, monthly, yearly, quota_pack}
  - status: select {unused, active, revoked}
  - stripe_order_id: text（历史字段名保留，即便支付渠道不是 stripe）
  - activated_at: date
  - campaign_source: text
要求：
- 支付成功：创建或激活 license（status=active，activated_at 写入）
- revoked：必须立即失效（/license/check 返回 valid=false）。

### 4.4 license_bindings（授权绑定设备）
- collection: `license_bindings`
- 字段：
  - license_id: relation -> licenses
  - device_id: relation -> devices
  - bind_fingerprint_hash: text（更强的指纹hash，可选）
  - ip_address: text
  - bind_time: date
要求：默认 1 license 绑定 1 device（可扩展多设备但要显式规则）；/license/check 必须校验绑定关系。

### 4.5 orders（订单）
- collection: `orders`
- 字段：
  - order_id: text（对外订单号）
  - product_id: relation -> products
  - device_id: relation -> devices
  - order_type: select {monthly, yearly, lifetime}
  - amount: number
  - status: select {unpaid, paid}
  - hupi_id: text（支付平台订单id）
  - pay_time: date
要求：
- create_order：写 status=unpaid
- notify/callback：验签后更新 status=paid、pay_time、hupi_id，并触发 license 发放/激活。

### 4.6 device_usage（用量/扣量）
- collection: `device_usage`
- 字段：
  - device_id: relation -> devices
  - product_id: relation -> products
  - log_date: text（YYYY-MM-DD）
  - used_quota: number
要求：按 (device_id, product_id, log_date) 聚合更新 used_quota；check_license 返回 used_today 与 daily_limit。

### 4.7 telemetry_logs（埋点/日志）
- collection: `telemetry_logs`
- 字段：
  - app_id: text
  - region: text
  - device_id: text
  - event_type: text
  - app_version: text
  - license_key: text（注意：建议存 hash，避免完整敏感信息）
要求：用于分析漏斗、崩溃、转化；日志不得记录密钥/支付敏感字段。

### 4.8 flovico_monitor（监控）
- collection: `flovico_monitor`
- 字段：
  - app_id: text
  - region: text
  - device_id: text
  - event_type: text
  - app_version: text
要求：用于健康检查/版本分布/异常事件。

### 4.9 users（PocketBase auth）
- collection: `users` (auth)
- 规则：list/view/update/delete 基于 `@request.auth.id` 绑定自身
要求：这是后台账号体系；客户端一般不直接使用。

---

## 5. 服务端 API 契约（必须实现，字段可扩展）
你必须实现并在代码里集中声明 API schema（便于未来升级），并确保客户端全部走 EmpireClient。

### 5.1 GET /config?product_id=...
返回：
{
  "product_id": "...",
  "latest_version": "1.2.3",
  "force_update": true/false,
  "download_url": "...",
  "support_contact": "...",
  "pricing": {...},
  "auth_policy": {
     "mode": "STRICT_ONLINE|GRACE_PERIOD|OFFLINE_PRO",
     "grace_hours": 24
  },
  "ui": {"ads_text": "...", "announcement": "..."},
  "features": {...}
}

### 5.2 POST /billing/create_order
请求：
{ "product_id": "...", "device_id": "...", "order_type": "monthly|yearly|lifetime", "client_version": "..." }
返回：
{ "order_id": "...", "pay_url": "...", "qrcode_base64": "...", "expires_at": "..." }

### 5.3 GET /billing/check_order?order_id=...
返回：
{ "status": "pending|paid|expired|failed", "license_key": "..."? }

### 5.4 POST /billing/notify  （支付平台回调）
- 必须验证签名
- 支付成功后：
  - 记录订单
  - 生成/激活 license_key
  - 绑定 device_id
  - 返回平台要求的成功响应

### 5.5 POST /license/check
请求：
{ "license_key": "...", "product_id": "...", "device_id": "...", "client_version": "..." }
返回：
{
  "valid": true/false,
  "plan": "trial|monthly|yearly|lifetime",
  "expires_at": "..."/null,
  "quota": { "daily_limit": 3, "used_today": 1, "unlimited": false },
  "offline_ticket": "..."?
}

### 5.6 POST /usage/report
请求：
{ "license_key": "...", "product_id": "...", "device_id": "...", "action": "core_action_name", "units": 1, "ts": 1234567890, "sig": "..." }
返回：
{ "ok": true, "quota": {...} }

---

## 6. 客户端关键行为（必须按顺序执行）
启动流程：
1) 读取本地版本号 current_version
2) 拉取云配置 /config（失败则走缓存/默认）
3) 检查强制更新（需要则弹窗并退出核心功能）
4) 初始化 device_id、读取本地 license_key
5) 初始化授权策略（STRICT/GRACE/OFFLINE）
6) 启动 UI

使用流程（每次执行“可计费动作”之前）：
1) `preflight_check()`：
   - STRICT：/license/check 验证 + 判断 quota；断网则不可用
   - GRACE：离线票据有效则放行；否则联网刷新
   - OFFLINE：验证本地签名许可；必要时偶尔联网校验防滥用
2) 执行业务动作（真正干活）
3) `post_usage_report()`：成功完成后再 report_usage
4) quota 用尽：弹出支付墙

---

## 7. 质量要求：你必须自己写测试、自己跑测试、自己做打包冒烟
### 7.1 单元测试（必须）
- EmpireClient：超时/重试/错误码映射
- license 流程：trial / paid / 过期 / device 绑定异常
- quota：每日重置逻辑、扣量逻辑
- 更新策略：force_update 触发行为
使用 pytest，并在 scripts/run_tests.ps1 一键运行。

### 7.2 集成测试（必须，含本地服务端）
- 启动本地 server（或使用 TestClient）
- 模拟 create_order -> check_order pending/paid
- 模拟 check_license 与 report_usage
- 验证客户端行为：quota 用尽会弹支付墙（用状态机/信号测试，不要求真点 UI）

### 7.3 打包冒烟测试（必须）
你必须提供：
- scripts/build.ps1：调用 PyInstaller 打包
- scripts/smoke_test.ps1：运行打包产物做最小验证
冒烟测试至少验证：
1) 程序能启动到主窗口（或无 UI 模式启动）
2) 能成功拉取云配置（可 mock）
3) 能执行一次“核心动作”的 dry-run（不一定真处理文件，但要跑通管线）
4) 不因缺失 DLL/模型/依赖而崩溃

最终必须告诉我：执行哪些命令可以一键完成“测试->打包->冒烟”。

---

## 8. 打包稳定性规则（你必须遵守）
- 任何大依赖（torch/cuda/rembg 等）必须：
  1) 提供 CPU fallback
  2) 提供可选安装/可选功能开关（云配置 features 控制）
- PyInstaller 必须显式处理：
  - hiddenimports
  - data_files（模型文件/资源）
  - Qt 插件路径
- 你必须在仓库中写清楚：`PYINSTALLER_NOTES.md`
  - 常见报错与解决策略
  - 需要包含的 DLL/依赖

---

## 9. 安全与配置（强制要求）
你必须创建 `.env.example`，至少包含：
- PB_ADMIN_EMAIL
- PB_ADMIN_PASSWORD
- PAYMENT_APPID
- PAYMENT_APPSECRET
- SERVER_SIGNING_SECRET
- DATABASE_URL（若需要）
所有真实值由我自行填写，禁止你把任何明文凭据写进代码/提交。

此外：
- license_key 生成必须可验证（推荐：服务端签名 JWT 或自定义签名字符串）
- /usage/report 必须有签名校验（避免任意刷扣量/伪造）
- 关键接口加 rate limit（最低线）

---

## 10. 离线交付要求（重要）：方案 A（最推荐）补丁包 + 一键脚本
由于我的 VSCode 电脑网络原因无法直接连接 Codex，你必须用“离线搬运”交付方式让我把成果复制到本地即可运行。

### 10.1 你必须输出的交付物（缺一不可）
在你完成改造后，你必须生成并输出以下文件（放在仓库根目录或 /deliverables）：

1) `patch.zip`
- 含：你新增/修改的所有文件（按目录结构组织）
- 不包含：任何真实密钥、任何 .env 真实值、任何用户隐私数据

2) `scripts/apply_patch.ps1`
- 功能：在我本地项目根目录一键应用补丁
- 行为要求：
  - 自动备份被覆盖文件（例如备份到 `_backup_YYYYMMDD_HHMMSS/`）
  - 解压 patch.zip 到临时目录
  - 覆盖/合并文件到当前仓库
  - 输出清晰日志：覆盖了哪些文件、失败原因
  - 完成后提示下一步命令：run_tests -> build -> smoke_test

3) `scripts/run_tests.ps1`
- 功能：创建/激活 venv（如需要），安装 requirements，运行 pytest
- 失败时必须退出码非 0

4) `scripts/build.ps1`
- 功能：用 PyInstaller 一键打包
- 必须在脚本中输出：产物路径、版本号、必要的依赖检查结果

5) `scripts/smoke_test.ps1`
- 功能：运行打包产物进行冒烟验证（第7.3节要求）
- 失败时必须退出码非 0

6) `PATCH_NOTES.md`
- 列出：
  - 你修改/新增的文件清单
  - 为什么改（目的）
  - 怎么验证（命令）
  - 已知风险/下一步建议

### 10.2 我本地的固定执行流程（你必须保证可用）
我在本地只做这几步：
1) 把 `patch.zip` 与 `scripts/*.ps1` 复制到项目根目录（或你指定位置）
2) PowerShell 运行：
   - `powershell -ExecutionPolicy Bypass -File scripts\apply_patch.ps1`
   - `powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1`
   - `powershell -ExecutionPolicy Bypass -File scripts\build.ps1`
   - `powershell -ExecutionPolicy Bypass -File scripts\smoke_test.ps1`

你必须保证：在干净环境下（只装 Python + VSCode），按上述流程能跑通到打包成功。

### 10.3 你对“不要让我反复测试”的承诺（硬指标）
- 任何功能改动必须伴随测试
- UI 行为要用状态机/信号/逻辑层测试覆盖（不要求真实点 UI）
- 你不能把“需要我来测”当作交付；必须给自动化脚本

---

## 11. 交付清单（你最后必须输出）
你完成改造后，必须输出：
1) 新产品已集成帝国底座：支持 config、update、paywall、license、usage
2) tests 全绿（至少给出运行日志摘要与命令）
3) build 脚本与 smoke test 脚本
4) 离线交付物：patch.zip + apply_patch.ps1 + PATCH_NOTES.md
5) 我只需执行第10.2节的 4 条命令即可完成上线前验证

---

## 12. 你的工作方式（Codex 必须遵守）
- 先读现有项目结构与入口（main.py / server/main.py）
- 再按本说明书抽象出 empire 模块与 server services
- 任何功能改动必须伴随测试
- 若遇到 GPU/依赖导致打包不稳定：优先保证 CPU 模式可打包可卖，GPU 做为可选增强（features 开关）

---

## 13. 备注：产品业务逻辑如何接入（留空由我填）
你需要在 /app/core/business_action.py 提供统一入口：
- run_action(input_files, options) -> result
并在其中标记：
- 哪一步是“计费动作”
- 哪一步需要 preflight_check 与 post_usage_report

业务功能占位：
<PRODUCT_BUSINESS_LOGIC_PLACEHOLDER>

---

# 结束：现在开始干活
你要做的是：把目标 GitHub 项目改造成上述结构，并确保测试/打包/冒烟全自动通过。