# Mihomo v1.19.31 探测、预认证与独立出口订阅补丁

基于 [MetaCubeX/mihomo v1.19.31](https://github.com/MetaCubeX/mihomo/tree/v1.19.31)，准确 revision 为 `ab405bad5beeeac8b003bb01f60f134f6df54471`。原始源码归档 [mihomo-v1.19.31.tar.gz](../source/mihomo-v1.19.31.tar.gz) 保持原样，SHA-256 为 `676732158479254de38ea5a78aa32ff650ce2d3a78156a0edc2ff0cb5c2ddfd8`。修改以 [独立补丁](mihomo-v1.19.31-probe.patch) 分发，继续适用上游 GPL-3.0。

此版本标记为 `v1.19.31-pocket-subscriptions1`。保留 `pocket-probe1` 的探测逻辑，另增加显式启用的固定出口预认证连接池及严格的 SOCKS 命令回复校验。入口、固定出口、凭据和 TLS 证书验证沿用用户配置。不能据此宣称用户真实线路从 400 ms 降至 100 ms。

## 入口与出口订阅身份

继续使用原 Mihomo provider/parser。每个叶子代理的私有控制 API JSON 增加 `configFingerprint`（完整 64 位 SHA-256）和 `configFingerprintVersion: 1`，不包含原始配置、密码或订阅地址。它基于原协议的 typed options 进行 canonical JSON 编码，保留服务器、端口、真实认证 UUID/密码、TLS、传输和启用的 mux 配置；名称、程序生成的 dialer/pocket 参数及运行时随机 ID 不参与身份。map 插入顺序不影响身份，数组和真实 HTTP/WS header 保持原样。原随机 `id` 与预认证运行时指针身份继续使用，不能用持久指纹替换路线失效代次。

应用管理的出口 provider 可设置以下受信 override；订阅行中的所有 `pocket-*` 大小写/下划线别名均清除，表达式结束后再次清除，然后仅注入显式 override。入口 provider 和 catalog 默认没有连接池。

```yaml
proxy-providers:
  ExitSource:
    type: file
    path: private-exit-snapshot.yaml
    override:
      pocket-config-fingerprint: <所选源节点的完整 SHA-256>
      dialer-proxy: EntryChoice
      proxy-name:
        - pattern: '^.*$'
          target: FixedExit
      pocket-preconnect: true
      pocket-preconnect-epoch-file: /应用私有环境目录/network-epoch
proxy-groups:
  - name: FixedExit
    type: select
    use: [ExitSource]
    filter: '^FixedExit$'
    empty-fallback: REJECT
```

按所选原配置的指纹筛选，必须恰好匹配一个 SOCKS5 节点，且不启用 smux。缺失、凭据/线路配置变化、多个相同配置别名或不支持的协议都拒绝，不能转用另一出口或直连；可同时加安全原名 filter 来明确选择重复配置中的指定别名。所选模式忽略无关的坏节点，仍对真正缺失的所选节点失败关闭。普通 provider 保持原同名去重与合法 override 兼容。

`ProbeExitN`/`WebProbeExit` 使用独立 provider 与同名顶层 selector，显式关闭预认证。真实 URLTest trace 仍绕过池，并且不会取用或补充业务 ready socket。此版本不开放其他协议作为订阅固定出口，不更换 TLS/QUIC/代理协议实现。

## 固定出口预认证

仅 `FixedExit` 的 `pocket-preconnect: true` 和有效私有 `pocket-preconnect-epoch-file` 同时存在时启用。捕获实际入口叶子、选择器修订号、内核配置代次及默认网络代号；复杂或不可冻结的路线、缺失或 blocked 代号使用原受保护建连方式。

真实 TCP 连接成功后最多准备一个未发目标 CONNECT 的认证 socket；最多一个准备任务，含准备的总期限 8 秒。没有定时补满。借出只使用一次，进入网站 TLS/HTTP 后从池所有权中移除，池失效不会关闭已交给调用方的连接。

旧闲置 socket 的 EOF/reset 仅在调用方尚未获得连接时，允许一次原冻结路线重建。认证拒绝、非零 SOCKS REP、协议异常及路线失效不重试；这些池路线的终止错误也会停止上游监听器的外层拨号重试。原普通路线和 URLTest 保持原重试策略。任何已交给调用方的浏览器数据都不自动重放。

`ClientHandshake` 顺序调用分拆的 `ClientAuthenticate` 与 `ClientCommand`；合法握手字节保持兼容。命令回复验证 VER、RSV 和 REP，避免把服务器拒绝当作成功。未更改 UDP 路径、目标证书校验或认证字段长度策略。详细身份、失效及实测边界见 [架构方案](../../docs/NETWORK-PRECONNECT-ARCHITECTURE.md)。

URLTest trace 显式绕过池的取用和补充，不让提前准备改变原测速口径。

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

补丁保留十项原 HTTP/TLS/取消主测试及 36 项协议、实际选择器、池并发与监听器重试主测试，并增加 7 项稳定身份与 11 项出口选择/真实 provider-group-listener/API 线路测试。重建时全部 64 项必须通过一次；测试源码和二进制来自同一份补丁，独立构建日志绑定所有通过记录。

Linux 双 SOCKS fixture 验证探测机制，不代表 Android 上已验收，也不代表用户节点的实际速度。正式版本还必须通过真实 Android 双 SOCKS、受保护浏览器连接连续性和对应源码的应用回归。

## Bounded burst preparation (2.0.7)

`pocket-preconnect-capacity` defaults to one and clamps to four for the named FixedExit only. The app uses four for both manual and provider-backed fixed exits. A mutex reserves a ready slot before other requests can take it; no caller waits for preparation. A successful real CONNECT refills missing slots once, retaining the existing eight-second TTL and route/network/cancellation gates. URL-test traffic still bypasses the pool. The burst tests cover simultaneous reservation, real socket timings, no target payload during preparation, no periodic refill, invalidation and capacity clamping. This is a new-connection optimization, not a reduction of a healthy reused-connection WAN RTT.
