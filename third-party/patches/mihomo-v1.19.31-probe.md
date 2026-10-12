# Mihomo v1.19.31 探测补丁

基于 [MetaCubeX/mihomo v1.19.31](https://github.com/MetaCubeX/mihomo/tree/v1.19.31)，准确 revision 为 `ab405bad5beeeac8b003bb01f60f134f6df54471`。原始源码归档 [mihomo-v1.19.31.tar.gz](../source/mihomo-v1.19.31.tar.gz) 保持原样，SHA-256 为 `676732158479254de38ea5a78aa32ff650ce2d3a78156a0edc2ff0cb5c2ddfd8`。修改以 [独立补丁](mihomo-v1.19.31-probe.patch) 分发，继续适用上游 GPL-3.0。

此版本标记为 `v1.19.31-pocket-probe1`。它修改控制端的线路探测，不修改网站流量转发、代理协议、入口选择、固定出口或 TLS 证书验证。不能据此宣称用户真实线路从 400 ms 降至 100 ms。

## 修复行为

上游统一延迟会先完成一次 HEAD，再尝试第二次请求。如果第二次失败，它保留第一个响应，但返回的耗时包含首次建链、第一次请求和第二次失败等待。本补丁在第一次 HEAD 完成时保存耗时，失败回退仅返回这个有效响应的时间。第二次失败的等待另记，不再算进成功响应的延迟。

上游探测的 HTTP transport 每次拨号都返回第一次预拨的 socket。服务器关闭连接后，后续请求会拿到已经关闭的 socket。本补丁只让第一次拨号领取预拨连接，后续拨号仍调用同一个代理的 `DialContext`，使用同一目标的 metadata 副本。重新建立的链会明确标记为冷复测。

所有尝试共享控制请求的总预算和取消状态。控制连接关闭时，在途 native HEAD 和新增探测连接会结束。新增连接有独立所有权，HTTP transport 异步拨号在取消后迟到完成，也会立即关闭。应用内真实浏览器的连接和 WebSocket 不属于这些探测连接。

## 向后兼容的控制 API

保留 `Proxy.URLTest(ctx, url, expectedStatus) (uint16, error)`、`/proxies/{name}/delay` 路径和原 `delay` 字段；在响应中增加 `probe` 对象，`schema` 为 `1`。

| 字段 | 含义 |
| --- | --- |
| `firstMs` | 首次有效 HTTP 响应耗时，包含代理链建立；无响应为 `-1` |
| `warmMs` | 第二阶段实际耗时，未尝试为 `-1`；失败时是等待失败所用的时间 |
| `totalMs` | 整次 native 探测的单调时钟耗时 |
| `warmAttempted` | 是否开始第二阶段 |
| `warmSucceeded` | 第二阶段是否获得满足 `expected` 的 HTTP 响应 |
| `secondConnectionReused` | HTTP transport 最后一次 `GotConn.Reused` 的真实结果 |
| `firstStatus` / `secondStatus` | 实际 HTTP 状态，无响应为 `0` |
| `dialCount` | 实际代理 `DialContext` 调用数，包含失败拨号 |
| `attempts` | `httptrace.WroteHeaders` 次数，包含已有 HTTP transport 的 HEAD 重试 |
| `warmError` | 固定枚举：空字符串、`cancelled`、`timeout`、`transport` |
| `error` | 可选的首阶段/最终错误类别；不会复制原始错误、URL 或凭证 |

`kind` 区分四种情况：

- `warm`：第二阶段成功，且实际复用了连接；`delay == warmMs`。
- `cold-retest`：第二阶段重新建链后成功；`delay == warmMs`，包含新链建立时间。
- `cold-fallback`：第二阶段失败；`delay == firstMs`，失败等待仅保留在 `warmMs` 和 `totalMs`。
- `first`：仅首阶段，或首阶段未完成。首阶段失败时仍返回失败的 HTTP 状态，不能作为健康线路接受。

健康判断保留原始 `expected` 状态与对应 URL 的新鲜 history。首次响应不符合 `expected`、但第二次符合时，保留上游接受最终响应的语义；不能简单要求所有 warm 的 `firstStatus` 都为 `204`。第二阶段收到错误 HTTP 状态时，`warmSucceeded` 为 `false`，对应 history 不健康。控制请求超时仍返回 `504`，首阶段 TLS 拒绝仍返回 `503`。

HTTP transport 的已有 HEAD 自动重试只用于无副作用的探测请求，没有增加自定义重试循环；所有重试共享总预算。它不会重发用户的聊天消息。

## 构建与核验

```sh
# 正常 APK 构建只执行快速只读核验，无需下载原生工具链。
python3 tools/build-mihomo.py --verify

# 独立重建、运行原生回归，并同时写入两个 Android ABI 和 receipt。
python3 tools/build-mihomo.py --build --target all --test --install
```

[构建脚本](../../tools/build-mihomo.py) 固定 Go `1.26.8`、NDK `29.0.13113456`、Android API `26`、`CGO_ENABLED=1`、`with_gvisor`，采用 `-p=4`、`-trimpath`、`-buildvcs=false`，保留原始 `go.mod` 和 `go.sum`，运行 `go mod verify`。工具链归档有固定 SHA-256；所有缓存默认位于 `work/mihomo-build`，不修改 HOME。固定的 BuildTime 是上游 source revision 的时间标记，实际验收时间以验收记录为准。

[构建 receipt](mihomo-v1.19.31-probe-build.json) 记录归档、补丁、模块校验和、构建参数和两 ABI 的 SHA-256。`--verify` 核验 source/recipe、文件路径白名单、当前二进制及 Android PIE/linker64/16 KiB 页对齐。独立源码重建后比较二进制 SHA 才能证明构建一致性；receipt 本身不代替运行验收。

补丁包含十项真实本地 HTTP/TLS/取消测试，覆盖正常同连接 warm、Connection close 后的真实冷复测、第二阶段 RST 回退、deadline、主动取消、TLS 拒绝、错误状态、首次错误而第二次成功、迟到 redial 连接的关闭，以及错误类别的隐私边界。

Linux 双 SOCKS fixture 验证探测机制，不代表 Android 上已验收，也不代表用户节点的实际速度。正式版本还必须通过真实 Android 双 SOCKS、受保护浏览器连接连续性和对应源码的应用回归。
