# 受控 HTTPS 请求身份检测服务

这是可自行部署的参考服务，没有内置或默认在线检测站。应用只在用户明确打开检测文档并采集时使用它。它记录检测站自己的顶层文档、Dedicated Worker 脚本与 Worker `fetch` 请求，不能代表 ChatGPT 官网、跨源页面、Shared Worker、Service Worker 或全部网络路径。

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

`result` 返回 `schema: 1`、`protocol: pocketchat-request-identity-v1`、nonce、时间、`events`、`credentialObserved` 及 `status`。未齐为 HTTP 202 / `pending`，三类探针齐全为 HTTP 200 / `ready`，敏感头、重复探针或事件超限为 `rejected`。重复的正常 `result` 轮询不追加事件；后来出现的敏感头仍会拒绝检查。

每个事件保留 UA、Accept-Language、Sec-Fetch-Dest/Site 和 TLS socket 对端，均与 nonce、来源、实际到达时间一起记录。文档与 Worker 的 JavaScript UA／语言通过页面消息单独交给应用，不放进服务端 HTTP 记录。应用读取结果的控制请求实际来自可信扩展后台，使用 `credentials: omit`、无来源标记并禁止重定向；原生端绑定环境与配置，不能将原生配置值描述成 Java HTTP 请求头观测。服务仅按固定结果路径将该请求中性标为 `control-result`，不根据此标签声称已鉴定 HTTP 发起者。检测文档完成后仍响应同窗口、同来源、同 nonce 的 `pocketRequestIdentityCollect` 消息，避免采集按钮打开较晚就丢失结果。它不会自动导航返回聊天。

服务端固定路径标记配合已知检测脚本提供来源证据，仍依赖用户信任该 HTTPS 服务及其部署；它不是对不可信服务的不可伪造证明。服务端记录、网页 JS、原生配置需要分别保留。只有真正的 Android／Gecko 专项运行才能证明当前客户端实际执行了 Dedicated Worker，Node HTTP 协议测试不能证明这一点。

## 有界资源与测试

检查状态最多保存 30 秒、64 个并发 nonce、每个 nonce 12 个事件。最多保留 4096 条可选全局日志事件，超出后明确记录 `dropped`，不继续扩大日志。HTTP 头、URL、读取时间、连接数和每连接请求数也受限制。UA 超过 2048 字符、Accept-Language 超过 1024、Sec-Fetch-Dest/Site 超过 64 时，检查会以 `header-value-too-long` 拒绝；不将截断内容冒充完整 HTTP 值，也不保存超限原值。公网运维还需相应的访问控制与流量防护；这些限制不等于完整服务加固。

```sh
node --test tests/request-identity/request_identity_server_test.cjs
```

测试生成短期本机证书，客户端显式信任该 CA，使用真实 TLS 请求核对头部来源、敏感头拒绝、超时、容量、重复探针和独立 JSONL 对账。它不连接公网、不关闭全局 TLS 验证，不宣称真实浏览器、手机、Dedicated Worker 或整体防泄漏验收。

需要与其他服务共同使用时可导入 `createIdentityService`（别名 `createIdentityServer`）。返回 `{server, log, snapshot(nonce), close()}`；`server` 是 `https.Server`。可选同步 `onUnhandled(req, res)` 或 `extraHandler(req, res)` 仅接管未知路径，返回 `true` 表示响应由宿主处理。该接口不能覆盖任何已知检测端点的检查规则，也没有 CLI 开关暴露测试路由。
