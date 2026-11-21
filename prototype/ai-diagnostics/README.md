# 新建本地诊断 mock

本机 mock 用于复现诊断网关的合成请求和响应。

当前只处理浏览器原生回调的严格白名单证据。没有真实供应商网络客户端、真实密钥读取、配置回写、工具执行或自动操作网页。`openai` / `deepseek` 只选择合成 Responses 契约分支，不会收费或向供应商发请求。

## 运行与测试

在仓库根目录运行：

```sh
python3 -B -m unittest discover -s prototype/ai-diagnostics -p test_diagnostic_gateway.py -v
python3 -B prototype/ai-diagnostics/diagnostic_gateway.py --port 8766 --token local-synthetic-token-0000000000000001
```

固定监听 `127.0.0.1`，不支持更改监听地址；没有环境变量配置。上述令牌是公开的本地合成示例，不是供应商密钥，格式与 Android 一致：`[A-Za-z0-9._~-]{32,256}`。不要把真实 API 密钥传给此程序。

本机入口为 `http://127.0.0.1:8766/v1/diagnose`。Android 正式路由仅接受用户配置的 HTTPS，因此这个 HTTP mock **不能直接用于手机正式发送**；它适用于内存协议和合成客户端验收。真实服务端客户端、付费启用门槛和 Android 结构化结果见 [Responses 说明](RESPONSES.md)。这个 mock 入口仍只做合成验证。

## 精确协议

方法和路径：`POST /v1/diagnose`，不接受尾斜杠或查询参数。

```text
Authorization: Bearer local-synthetic-token-0000000000000001
Idempotency-Key: 12345678-1234-4234-8234-123456789abc
Content-Type: application/json
Content-Length: 实际UTF-8正文长度
```

外层只能有 `version:1`、`provider:"openai"|"deepseek"`、`evidence:[Entry]`，最多 3 个标签条目。Entry 必须完整匹配 Java `AiDiagnosticEvidence.Entry.json()`：

```json
{"version":1,"provider":"openai","evidence":[{"schema":1,"engine":"GECKO","tabEvidenceId":"T1","scope":"TAB_CALLBACK_OBSERVATIONS","navigationAttribution":"UNKNOWN","events":[{"id":"E1","kind":"LOAD_ERROR","signal":"UNKNOWN","code":null,"category":null,"elapsedMs":123}]}]}
```

每页最多 16 条事件，允许空列表。标签编号为正整数 T1..T2147483647；事件编号为 E 加 1..19 位非零开头数字，同页内唯一。事件类型、信号值、整数范围与原生证据契约严格检查；错误码与类别必须同时存在或同时为空。无原始码时只能是 UNKNOWN。响应中引用按 T/E 组合区分。所有额外键、URL、域名、正文、环境真实标识、未知枚举与重名 JSON 键都会被拒绝。只认 `GECKO`，不把未发布 Chromium 当作可用能力。

成功只返回 `{"reply":"..."}`，最多 6000 字符。确认部分来自原生回调字段；可能原因始终标为未证实。原生 `navigationAttribution` 固定 UNKNOWN：即使有 DNS/超时/TLS 等信号，也不能确定具体文档或网络阶段。输出不包含指令执行能力。

失败只返回固定 `{"reason":"..."}`，不反射正文、异常、令牌或原始供应商信息。主要状态：400 格式无效、401 未授权、404 路径错误、405 方法错误、409 同 ID 不同正文或处理中、413 超限、502 合成响应无效、503 容量已满、504 到达期限。

## 去重、期限和边界

- canonical 小写 UUID 与**精确原始正文的 SHA-256**绑定；改变供应商或任何字节后不能复用同一 ID。相同预览重试须复用原始正文及 ID。
- 进程内最多缓存 256 个请求，不自动淘汰。已完成和超时都缓存最终结果；迟到完成不会覆盖超时；同 ID 不会再次执行合成客户端。
- 同 ID 正在处理时返回 409。达到容量时拒绝新 ID，而不是偷偷丢弃去重记录。进程重启即丢失缓存，因此**不是持久化幂等保障**，不能直接用于真实付费 API。
- 默认每次合成处理期限 3 秒，最多 4 个 worker。超时不等于取消 Python 线程；迟到输出被丢弃，卡住的线程仍占槽位，避免无限增殖。
- 正文最大 64 KiB、连接最多 8 个、每连接总寿命 10 秒、socket 空闲超时 5 秒。关闭客户端连接不意味着工作已取消；复用同一 ID 可获取缓存结果。真机连接使用 [设备验收步骤](ACCEPTANCE.md)。
- HTTP 适配及去重测试使用内存流、fake client 和纯合成数据；测试不打开 socket。

## Responses 契约依据

2026-11-21 核对 [OpenAI Responses 创建文档](https://developers.openai.com/api/reference/resources/responses/methods/create) 与 [DeepSeek Responses 文档](https://api-docs.deepseek.com/guides/responses_api/)。合成请求使用独立 `instructions`、数据 `input`、`text.format` 的严格 JSON Schema、`tools:[]`、`tool_choice:"none"`、非流式输出。OpenAI 分支 `store:false`；DeepSeek 分支省略不支持的 `store`。

默认模型名 `synthetic-contract-model` 是明确的合成占位，不宣称真实模型存在或已验证。响应只接受完成的 assistant text；refusal、incomplete、工具项、额外或缺失证据、改变信号值均失败。当前返回的自然语言由本地规则生成，合成 API 只贯通结构契约，尚没有真实模型生成解释。
