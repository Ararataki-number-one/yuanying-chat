# 受控 HTTPS 合成验收网关

此脚本用于阶段二 Android 的 `/v1/diagnose` 接口验收。响应是 `{"version":2,"diagnosis":{"hypotheses":[...]}}`；每个选中标签最多返回一条固定的 `INSUFFICIENT_EVIDENCE` 和 `REVIEW_LOCAL_DIAGNOSTICS`。没有故障回调时返回空列表。它不调用模型，不导入付费客户端，不使用供应商密钥，也不发出外部连接。

## 本机自动验证

```sh
python3 -B prototype/ai-diagnostics/test_acceptance_https_gateway.py \
  --report work/ai-acceptance/tls-loopback-results.json
```

依赖 Python 3 标准库及本机 `openssl` 命令。测试仅连接 `127.0.0.1`，临时生成合成证书并自动清理；信任仅加入测试客户端自己的 `SSLContext`。不修改宿主系统或 Android 的信任库。

测试覆盖真实 TLS 成功链路、默认信任拒绝合成证书、显式 CA 仍拒绝错域名、SNI 与 Host 检查、原始路径与重复头拒绝、慢握手并发和取消后的无内容日志。另用导入及连接守卫验证脚本不加载 `provider_gateway`、`responses_transport`、`responses_ledger`，且服务器构造与本地诊断处理不尝试外连或名称解析。报告区分本机 TLS、设备和供应商执行；测试通过不代表真机或公网线路已验收。

## 使用已有可信入口

操作者需要已有、受控的 HTTPS 域名及设备已经信任的有效证书、私钥和反向代理入口。脚本不会申请证书、创建公网监听、配置 DNS 或更改设备证书校验。

先准备独立测试访问令牌：32–256 个安全 ASCII 字符，存入权限为 `0600` 的普通文件。不要使用供应商 API key，也不要复用代码内的旧 demo token。该令牌仅供自己的测试手机访问此合成入口；不写进 APK、提交或日志。

```sh
python3 -B prototype/ai-diagnostics/acceptance_https_gateway.py \
  --endpoint https://YOUR_AUTHORIZED_HOST/v1/diagnose \
  --cert /PRIVATE_PATH/fullchain.pem \
  --key /PRIVATE_PATH/privkey.pem \
  --token-file /PRIVATE_PATH/acceptance.token \
  --port 8767 \
  --response-delay-ms 1500
```

路径和主机名由操作者替换为已有配置。加密私钥需要操作者先完成受控的服务端加载配置，本脚本不会提示输入私钥口令。监听地址固定为 `127.0.0.1`，没有公开绑定或付费模式参数。TLS 最低为 1.2。

已有受控反向代理须满足：

- 只转发精确 `/v1/diagnose` 到 `https://127.0.0.1:8767`；保留专用访问令牌、幂等编号及正确的 `Content-Length`。
- 上游 `Host` 与 `--endpoint` 的主机、端口一致；上游 TLS 的 SNI 使用同一主机名，并按已有可信 CA 验证证书。默认 443 可省略端口。IP 字面量没有 SNI，仍须通过客户端 IP SAN 校验。
- 限制入口请求大小为 64 KiB，并设并发及超时上限。禁记授权头、请求与响应正文；不要为了接入关闭证书验证或修改 Android 信任策略。

手机使用受控入口的完整 HTTPS URL 和专用测试令牌。仅用合成页面及匿名白名单证据逐次预览确认。成功响应带 `X-PocketChat-Acceptance: synthetic-no-provider`，其建议只是固定合成结果，不能用于声称模型能力通过验收。

## 切网、取消和观察计数

`--response-delay-ms` 默认 0，允许 0–3000 毫秒。用 1500 或 3000 毫秒给手机留出切网、切环境或取消操作的窗口；相同编号的完整缓存重放不再次延时。TLS 握手位于最多 8 个工作线程内，握手超时 3 秒；读取阶段继承 5 秒空闲及 10 秒总连接计时，响应后关闭连接。

标准输出只含启动状态及固定名称的整数计数：`received`、`completed`、`replayed`、`rejected`，不含正文、令牌、匿名请求编号或异常详情。`received` 表示经过基础协议校验并预留的新请求；`completed` 表示本地处理结束，可能包含错误结果，**不代表手机收到响应**。TLS 或 HTTP 解析阶段拒绝的连接不一定进入这些计数。

取消手机等待后，合成处理仍可能结束；应验证 Android 不把迟到结果显示到另一个环境或新证据上。服务器的幂等缓存只在当前进程内有效，最多 128 个请求，容量满返回 503。重启会清空缓存；这不替代阶段二持久账本，也不能改作付费网关。
