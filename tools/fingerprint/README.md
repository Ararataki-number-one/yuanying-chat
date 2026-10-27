# 受控 HTTPS 请求身份检测服务

这是可自行部署的参考服务，没有内置或默认在线检测站。应用只在用户主动检查服务或打开检测文档时使用它。它记录检测站自己的顶层文档、Dedicated Worker 脚本与 Worker `fetch` 请求，并支持单独选择的受控跨源图形页；不能代表 ChatGPT 官网、其他跨源页面、Shared Worker、Service Worker 或全部网络路径。

```sh
node tools/fingerprint/request_identity_server.cjs \
  --key /path/to/tls.key --cert /path/to/fullchain.pem \
  --host 0.0.0.0 --port 9889
```

证书须对手机信任，并覆盖实际主机名。示例配置地址为 `https://checks.example.net:9889/pocketchat-identity/v1/`，仅表示地址格式，不是可用检测站。默认监听 `127.0.0.1`；公开部署需由运营者明确选择监听地址、防火墙与运维方案。

服务直接终止 TLS，只将 `socket.remoteAddress` 标为 `socket-peer`。它不会信任 `X-Forwarded-For`。反向代理后的 socket 对端通常不是手机实际出口；此部署方式不能据此作出口一致性结论。

可选 `--output /new/report.json --raw-log /new/arrivals.jsonl` 保存独立服务端到达证据。两个路径必须不同且尚不存在，父目录需先建立。日志不保存 Cookie、Authorization、Proxy-Authorization、Referer 或 Origin 的内容；任意一个敏感头出现都会使该检查被拒绝，包括只有空值的敏感头。服务不设置 Cookie，不读取登录或聊天数据，也不会把网页 JavaScript 值当成 HTTP 头。

## 协议与来源

所有请求均为无正文的 GET。每次检查使用独立的 32 位十六进制随机 nonce：

| 路径 | 服务端记录来源 |
| --- | --- |
| `document?nonce=...` | `document`，检测站顶层文档请求 |
| `worker.js?nonce=...` | `worker-script`，Dedicated Worker 脚本请求 |
| `observe?nonce=...&source=worker` | `worker-fetch`，该 Worker 发出的请求 |
| `result?nonce=...` | 首次 `control-result`，应用的扩展后台独立取得上述服务端记录 |
| `capabilities?nonce=...` | 仅用户主动发起的服务连通性与协议能力检查，不创建身份观测记录 |
| `frame?nonce=...` | 显式配置的第二来源图形页；单独记录为 `cross-origin-frame`，不混入主文档／Worker 的三类请求 |

`result` 返回 `schema: 1`、`protocol: pocketchat-request-identity-v1`、nonce、时间、`events`、`credentialObserved` 及 `status`。未齐为 HTTP 202 / `pending`，三类探针齐全为 HTTP 200 / `ready`，敏感头、重复探针或事件超限为 `rejected`。重复的正常 `result` 轮询不追加事件；后来出现的敏感头仍会拒绝检查。

每个事件保留 UA、Accept-Language、Sec-Fetch-Dest/Site 和 TLS socket 对端，均与 nonce、来源、实际到达时间一起记录。文档与 Worker 的 JavaScript UA／语言通过页面消息单独交给应用，不放进服务端 HTTP 记录。应用读取结果的控制请求实际来自可信扩展后台，使用 `credentials: omit`、无来源标记并禁止重定向；原生端绑定环境与配置，不能将原生配置值描述成 Java HTTP 请求头观测。服务仅按固定结果路径将该请求中性标为 `control-result`，不根据此标签声称已鉴定 HTTP 发起者。检测文档完成后仍响应同窗口、同来源、同 nonce 的 `pocketRequestIdentityCollect` 消息，避免采集按钮打开较晚就丢失结果。它不会自动导航返回聊天。

服务端固定路径标记配合已知检测脚本提供来源证据，仍依赖用户信任该 HTTPS 服务及其部署；它不是对不可信服务的不可伪造证明。服务端记录、网页 JS、原生配置需要分别保留。只有真正的 Android／Gecko 专项运行才能证明当前客户端实际执行了 Dedicated Worker，Node HTTP 协议测试不能证明这一点。

## 主动检查服务能力

`capabilities` 返回本次 nonce、`schema: 1`、原协议名、`source: controlled-service-capabilities` 和 `status: ready`。`capabilities` 对象分别列出 `topLevelDocument`、`dedicatedWorker`、`boundedWorkerReply`、`crossOriginFrame` 和 `crossOriginFrameReceiver`；`limits` 列出 `checkTtlMs`、`maxConcurrentChecks`、`maxCheckEvents` 和 `workerResponseBytes`。缺少必需字段不表示支持。

这个端点不打开文档、不启动 Worker、不创建检查状态或身份事件。服务容量已满时返回 HTTP 429 / `detector-capacity`；收到凭据或来源标记为 403 / `credential-header-observed`；对照头过长为 409 / `header-value-too-long`。证书与一般连接错误可能在浏览器中只表现为同一种失败，应用不能凭 `fetch` 的异常把证书问题说成已经确认。

## 可选的受控跨源图形页

普通 `document?nonce=...` 不会嵌入其他来源。只有用户明确配置并同意第二 HTTPS 服务、应用核对其与主服务能力广告完全一致后，才使用固定的 `document?nonce=...&frame=1`。不要将服务器广告自动当成用户授权或可信配置。

两侧服务均需由运营者显式配置，示例域名仅表示格式：

```sh
# 主检测站：只允许这里声明的第二站点
node tools/fingerprint/request_identity_server.cjs --key /path/to/check.key --cert /path/to/check.pem --port 9889 \
  --frame-endpoint https://frame.example.net:9891/pocketchat-identity/v1/
# 第二站点：只允许这里声明的主站点嵌入
node tools/fingerprint/request_identity_server.cjs --key /path/to/frame.key --cert /path/to/frame.pem --port 9891 \
  --frame-parent-origin https://checks.example.net:9889
```

主站能力广告的唯一位置是 `capabilities.frameEndpoint`，`capabilities.frameParentOrigin` 来自当前 HTTPS 请求的规范化 Host；它必须与应用配置的主来源一致。第二站点的入站限制另列为 `capabilities.frameReceiverParentOrigin`。反向代理需保留实际主站 Host；服务不从转发头推断另一身份。

图形页没有任意代码、URL 或父来源查询参数。它使用固定 Canvas／WebGL 探针，CSP 仅允许精确的父来源，主站 `frame-src` 仅允许配置的第二来源；iframe 使用沙盒且不能自行跳转顶层。消息检查真实 `event.source`、`event.origin` 和 nonce。三秒内不可用、被 CSP 拦截或接口不存在时保留未覆盖，不放宽浏览器安全策略。

结果单独标为 `controlled-cross-origin-iframe`，Canvas 与 WebGL 的读回独立记录；不要求不同上下文的哈希相同，也不表示全部指纹保护通过。音频和字体不在这份跨源图形探针中采集。

## 响应与语言语义

检测 Worker 的 `observe` 响应采用流式读取，累计上限 **8192 字节**，之后才解码 UTF-8 和解析 JSON。五秒期限保持，超限会中止读取；没有可用的有界流接口时直接报告未覆盖／失败，不退回不受限的 `response.json()`。HTTP、传输、超时、字节超限、编码、JSON 与协议不符使用不同固定类别；不回传原始错误文本。

应用保留 HTTP 头原值，并另外比较完整语言列表：规范化大小写，按有效 q 权重排序，同权重保留原顺序，`q=0` 标为排除。重复范围、无效权重与有效通配范围不被当成完整列表通过；JavaScript 没有 q 权重，因此不会声称已从 JS 验证权重。原生配置缺完整语言数组时对应项仍为未覆盖，不用首选语言合成完整列表。差异可能来自隐私标准化，不能直接判断泄漏。

## 有界资源与测试

检查状态最多保存 30 秒、64 个并发 nonce、每个 nonce 12 个事件。最多保留 4096 条可选全局日志事件，超出后明确记录 `dropped`，不继续扩大日志。HTTP 头、URL、读取时间、连接数和每连接请求数也受限制。UA 超过 2048 字符、Accept-Language 超过 1024、Sec-Fetch-Dest/Site 超过 64 时，检查会以 `header-value-too-long` 拒绝；不将截断内容冒充完整 HTTP 值，也不保存超限原值。公网运维还需相应的访问控制与流量防护；这些限制不等于完整服务加固。

```sh
node --test tests/request-identity/request_identity_server_test.cjs
node --test tests/request-identity/worker_response_bounds_test.cjs
```

测试生成短期本机证书，客户端显式信任该 CA，使用真实 TLS 请求核对头部来源、敏感头拒绝、超时、容量、重复探针和独立 JSONL 对账。它不连接公网、不关闭全局 TLS 验证，不宣称真实浏览器、手机、Dedicated Worker 或整体防泄漏验收。

需要与其他服务共同使用时可导入 `createIdentityService`（别名 `createIdentityServer`）。返回 `{server, log, snapshot(nonce), close()}`；`server` 是 `https.Server`。可选同步 `onUnhandled(req, res)` 或 `extraHandler(req, res)` 仅接管未知路径，返回 `true` 表示响应由宿主处理。该接口不能覆盖任何已知检测端点的检查规则，也没有 CLI 开关暴露测试路由。

## 同手机标准与强化模式对照

本流程需要用户在同一台真实手机执行。云端主机、Chromium 或受控 Android 模拟器的结果不填写为手机验收。开始前记录应用版本、Android 版本、Gecko 版本、环境和来源；两次都使用手机版、相同语言列表与同一检测来源，保持网络配置和测试输入一致，避免把同时改变电脑版模式、来源或内核造成的差异归于保护等级。

1. 用户选择标准模式，在空闲网页打开“查看环境自检”，运行“检查图形与音频（本机）”，再点“复制深检原始记录”保存标准样本。需要长期参照时主动固定这份主页面深检。
2. 完成当前输入、回复和文件任务后，由用户选择强化模式，等待原生保护显示已确认，再在同一来源运行同一个深检并复制第二份记录。未确认或失败时保留该状态，不填写保护已生效，也不自动切回标准模式。
3. 逐项并列记录页面、同源 iframe 和 Dedicated Worker 的接口状态、限制原因、探针版本及有效输出；Worker 的音频、字体和本次跨源探针未覆盖的接口保留未覆盖。不同环境的哈希不要求相同；随机化或标准化都可能产生正常变化。
4. 两种模式分别手动核对下表。附件可选择小测试文件并检查上传状态，不自动发送聊天。切换模式前先手动保留草稿，记录切换时是否重载；登录保留与恢复结果按实际填表。应用不会自动重发聊天。

| 真实手机兼容项 | 标准模式 | 已确认的强化模式 | 现场说明 |
| --- | --- | --- | --- |
| 登录与登录状态保留 | 未执行 | 未执行 |  |
| 百度输入法、长文本与代码输入 | 未执行 | 未执行 |  |
| Canvas 绘制与读回 | 未执行 | 未执行 |  |
| 系统附件选择与网页上传 | 未执行 | 未执行 |  |
| 后台返回、页面恢复与阅读位置 | 未执行 | 未执行 |  |

复制内容是主动导出的诊断记录，包含公开浏览器信息和采样元数据；没有账号 Cookie、密码或聊天正文。固定参照只用于同组主页面比较；用户切换配置后会分别展示，不将跨配置差异直接判断为异常或泄漏。最终结论须同时说明设置回读、实际 API 观测和人工兼容结果，不能只凭其中一项。
