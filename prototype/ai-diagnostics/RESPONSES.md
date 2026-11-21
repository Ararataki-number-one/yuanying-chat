# PocketChat AI 诊断 · Responses 服务端候选

> 测试 APK 依赖状态、单条回归命令和手机 HTTPS 验收见 [当前验收说明](ACCEPTANCE.md)。

诊断候选独立于 2.1.15 维护发布渠道。

## 当前可用的本地验证

- `python3 -B -m unittest discover -s prototype/ai-diagnostics -p 'test_*.py'` 验证 mock、模型协议、固定 HTTPS 传输、SQLite 账本和网关。测试用的是合成凭据与供应商替身。
- `python3 -B prototype/ai-diagnostics/diagnostic_gateway.py` 仍在 `127.0.0.1` 启动原合成 mock，保留 `{"reply":"..."}` 响应，适合复现阶段一。Android 候选只呈现可核验的结构化第 2 版诊断。
- Android HTTP 客户端、线路和 Gecko 证据的 JVM 测试分别在 `tests/ai-diagnostic-gateway-host`、`tests/ai-diagnostic-route-host`、`tests/ai-diagnostic-evidence-host`。HTTP 客户端 runner 支持 `--wire-case 确认请求.json 网关回复.json`，可核对同一快照的跨层数据。
- 宿主验收用环回网关、SQLite、供应商替身和 Android JVM 解析器核对 Java 生成的匿名证据。设备上的 Gecko、DNS 和实际出口需要单独验收。

## 从证据到诊断

Android 在 `/v1/diagnose` 发送逐次预览确认的白名单快照。服务端只将标签页回调、结构化错误码、相对耗时和匿名编号作为单条数据输入。付费路径返回 `{"version":2,"diagnosis":{"hypotheses":[...]}}`。缺故障回调的快照得到空列表，省去模型调用。

模型只能选择受控假设、同一快照内的证据编号和只读建议。服务端验证模型 JSON、证据和错误信号搭配，拒绝工具项、拒答、截断、伪造引用和自由字段。Android 独立拒绝重复键、尾随内容、无效 UTF-8、过长回复、错位引用和不匹配的建议。界面以确认时的本地快照生成「本机观察」，单列「远端建议（待核实）」。具体导航和根因可保持未知。

OpenAI 固定调用 `https://api.openai.com/v1/responses`，使用结构化输出和 `store:false`。DeepSeek 固定调用 `https://api.deepseek.com/responses`，省略供应商未提供的 `store` 和未列出的 `format.strict`，仍经同一服务端严格验证。HTTPS 校验、无重定向和自动重试、全程截止及响应大小上限由传输层执行。超时尽力关闭在途连接，已发送请求仍可能被处理。官方文档为 [OpenAI Responses](https://developers.openai.com/api/reference/resources/responses/methods/create) 和 [DeepSeek Responses](https://api-docs.deepseek.com/guides/responses_api/)。

## 启用付费请求前的最低条件

1. **已授权网关和真实线路验收。** 为用户自己的精确 HTTPS `/v1/diagnose` URL 配置有效证书及固定入口。真实网关按该入口核对 HTTP Host。在自己的测试环境使用合成页面和受控网关，验证 DNS、实际出口、断网和切网中止。主机名检查和 Host 匹配只用于约束配置，实际解析目标和出口需要独立验证。现有浏览器规则优先使用显式外部代理，VPN 要求适用于无显式代理的外部模式。手机到网关与网关到供应商分别记录并验收。服务端出站由其部署网络控制，应部署在用户授权的出口并限制为两个固定供应商 HTTPS 目标。
2. **私有服务端凭据与持久账本。** 将专用网关访问令牌、稳定的独立账本 HMAC 密钥以及供应商密钥分别配置在自控服务端凭据存储。Android 只取得网关发放的访问令牌。首次通过 `Ledger(..., initialize=True)` 受控建立私有 SQLite，之后只打开原账本。备份恢复须保留最新去重记录。连接入口及反向代理的日志排除令牌、授权头、请求及回复正文。
3. **明确开启、额度、可见状态。** 由服务端入口注入 `ResponsesTransport(credential_provider)`，提供明确的模型名和账本，确认上述验收后才允许 `ProviderGateway(..., enable_paid_requests=True, device_route_accepted=True, provider_egress_accepted=True)`。这两个验收标志是运营设置，不能代替设备观察。mock 命令无付费启动开关。付费调用默认关闭。外部 HTTPS 入口须有自己的请求大小、并发和超时上限，与 Android 的连接与读取期限协调。
4. **丢失回包时的处理。** 同编号和同预览只预留一次调用，模型或预览改变会产生冲突。正常结束、超时或进程退出后保留不可重用记录。账本保留 HMAC 指纹、匿名请求编号和状态，不保存请求、回复、令牌或供应商密钥。过期处理只将进行中状态标成不确定。完成后响应正文无缓存，丢失时显示「已完成，结果没有保留」。容量满会暂停新请求，不能靠删除记录或回滚旧账本恢复付费流量。取消只停止手机等待，供应商处理状态可能未知。

Android 使用 [独立测试包与设备验收步骤](ACCEPTANCE.md)。
