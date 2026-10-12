# 1.5.20 · GeckoView 官方网页客户端

源码 `8d3149006857c53478970e89d832d90c18825387`。[修改说明](../../docs/CHANGELOG-v1.5.20.md)。

[正常 Android 构建与回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38210962350)：10 套实际 Android 报告、14 套主机报告共 464 项检查及五组同源码发布门槛全部通过。原报告保持原样，主机报告通过同一不可变构建 artifact 的字节一致性绑定源码，未补写虚构 source 字段。[完整证据与文件 SHA](evidence.json)。

- [实际 Gecko HTTP/2/TLS](gecko-pool-results.json)：按共享门槛验证同路线健康恢复复用连接，真正路线改变重新隔离，缺少核验凭据和未知网络仍拒绝请求。
- [实际 Android 原生探测](native-probe-results.json)：两层认证 SOCKS、真实 cold/warm socket 与拨号次数；复测 RST 不累计成成功延迟；四组取消要求目标观察到实际 native 关闭，并保留原 WSS、PID、入口和固定出口。执行内核 SHA 与本版 receipt 核对。
- [独立源码重建](independent-native-rebuild/mihomo-rebuild-results.json)：[独立 Actions](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38210962335) 重新生成两个 Android ABI，字节与提交的 receipt 一致，十项原生本地回归通过。此项不是 Android 运行证明。
- [官方 Firefox 157.0.1 SDK 输入](official-sdk-verification.json)：[固定 receipt](official-sdk-input.json) 与提交及 Gradle 实际解析的 AAR 一致，官方 SDK 的实际 BuildConfig 版本与 release 渠道经过核对，SDK 与类未做私有变换。这是构建输入证明，不是额外 Android 运行验收，也不表示偶发输入问题已修复。
- [当前原网页界面](ui-visual-results.json)：仅 GeckoView 与 ChatGPT 官方网页外层界面；19 张本版界面截图，顶部只保留菜单、环境与更多三项操作。历史界面未重建，未作为本版截图。
- [重新加载确认](compact-chrome-results.json)：八项同源码真实 Gecko 检查包含三个实际 Android 按钮点击；取消及对话变化后的过期确认保留原内容、完整输入和登录，明确确认后先归档输入并加载当前对话，空闲重载不弹窗。三次真实文档请求经过受控 SOCKS，未自动发送。
- [安静完成提醒](quiet-notification-results.json)：实际可见 Activity 与 Home 后进程状态核验；前台回复和下载完成不弹提醒，后台提醒默认关闭，主动开启后才提醒并去重。Android 必需的服务提示仍保持静默。
- [环境线路上的应用更新](update-route-results.json)：两个真实环境进程与双 SOCKS；原环境失效后停止实际下载 socket、保留进度和 ETag，恢复后用真实 Range 续传并核验签名；不会借默认环境直连。
- 既有交互、登录隔离、附件、下载、通知和应用更新续传通过同源码回归；图像和日志按固定白名单归档。

## 受控 Linux 证据与边界

[配置基线](controlled-linux/chain-performance/analysis.json) 保留旧基线源码标识：200 条双 SOCKS 连接中，应用与简化 Clash 等价配置没有显示天然多出的 300 ms；冷 HTTPS 与复用 HTTPS 是不同耗时阶段。[52 项原版/补丁 AB/BA](controlled-linux/probe-reuse-audit/trace-compare-report.json) 验证探测重新拨号、失败回退和原生取消。[原版失败机制](controlled-linux/probe-reuse-audit/warm-failure-report.json) 同时保留，未改成新版本通过结果。

这些均为 Linux 回环、合成节点和证书，没有真实账号或用户节点；它们不属于十套 Android 验收，也不能证明用户手机 400 ms 已降至电脑的 100 ms。复现需将两个受控目录放回独立 checkout 的 `work/`，按 binary receipt 获取官方内核并重新生成本地测试证书；归档没有私钥或大型 native 二进制。原始上游源码仍位于仓库 `third-party/source/`，本版补丁、recipe 与重建脚本在 `native-source/`。

## 原签名与公网下载

[下载 1.5.20 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.20-gecko/PocketChat-1.5.20-gecko-arm64.apk)。版本 code 46，118922262 字节；SHA-256 `f74dffd1bb108e20b5bfcc4135f273bb64435628284e40fb68c02bf3c8cc4292`，原证书 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。支持覆盖安装，环境账户及更新续传保留。

[原签名 APK 校验](apk-verification.json)、[匿名完整下载](public-download-verification.json)、[公网更新源](public-update-feed-verification.json) 和 [实际官方 CDN Range/If-Range](public-range-verification.json) 一致。没有将签名密钥或 API 令牌归档。

## 未解决与未覆盖

[1.5.19 偶发输入边界](known-input-boundary/README.md) 连同原报告、旧 source 与 artifact 保持原样。此前硬件按键光标回退仍未归因；本版正常回归通过不等于该偶发问题已修复，没有加入未经验证的 SDK 补丁。

此前输入与 SDK 候选调查继续保留在各自不可变历史 artifact；本版没有将候选补丁或历史诊断计入正常验收。

Android 15 x86_64 模拟器与合成 HTTP/2/TLS 网站用于验收。没有用户真机、真实账号、长时间现场使用或同 Wi-Fi/同入口/同出口的手机电脑对照；不承诺帧率、带宽或固定的 WAN 延迟改善。既有固定出口与失败拒绝保护保留，没有自动重发或直连回退。
