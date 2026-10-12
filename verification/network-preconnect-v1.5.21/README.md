# 1.5.21 · 固定出口连接预认证

源码 `a6c60f38fa51c107706626bae6707d2bd317c803`。11 套同源码实际 Android 报告、14 套主机报告 464 项检查和五组既有发布门槛通过；新增预认证由 [真实 Gecko/SOCKS/H2 报告](preconnect-results.json) 与共享 wire contract 验证。[不可变构建 manifest](manifest.json) 的原始 SHA 为 `818171be50515fa89b0328e40a5297e8ca8ebf15558471cec5a7f2787701fdee`；完整文件身份见 [evidence.json](evidence.json)。

[原始 Git blob 与首父源码绑定](projection/current-evidence-verification.json)、[严格投影](projection/final-projection-verification.json)、[五门槛摘要](projection/final-five-gate-results.json) 和 [本次 helper 快照](archive-helper.py) 保留归档过程；本目录没有复制 APK 分块或大型二进制。

准备阶段只完成固定出口的 SOCKS 方法与认证，不连接网站。一条连接只交付一次；实际请求仍完成目标 CONNECT、TLS 与 H2 响应。报告保留三组成对冷请求及真实 wire 时间、网络/入口代际清理、过期、错误认证、在途取消、测速绕过和原 WSS 持续收发。准备工作仍消耗网络、内存和电量；此处合成延时下的收益不代表用户 WAN 413 ms 或网站 3416 ms 已降低。

[独立 native 重建](independent-native-rebuild/mihomo-rebuild-results.json) 使用同源码、原始上游与提交补丁，两个 ABI 字节相同，36 项预认证及原 10 项探测回归各通过一次。它是重建/本地原生证明，不代替 Android 运行证据。官方 Firefox 157.0.1 SDK 的 receipt 与实际 Gradle AAR 相同，未做私有 SDK 改写。

[Python wire 调查](exploratory/python/results.json) 保留原源码 `7b99a1233a40bfadf9eece5d65b180e53b515773`，未运行生产 Mihomo/Android；[Go normal/race 调查](exploratory/go/native-validation-receipt.json) 保留冻结 source identity、日志 SHA、36 normal /36 race/原10与 clean-apply receipt，仅为受控机制调查，不计入本版 11 套 Android，也不作为公网速度结论。旧 1.5.20 归档和 200/52 基线未改写。

[完整 Linux 进程调查](exploratory/linux-process/manifest.json) 保留原 `140a9d8`、实际 Linux 二进制 SHA、wire、失败尝试及原时序定义；该 native 组件与最终源码字节相同，但不是最终源码 Android 验收或独立 Linux 可复现重建。[此前 Android 失败](historical-failures/android-140a/preconnect-results.json) 保留原不可变 artifact：十套既有回归通过，新预认证完成七项后遇到 Files.readString API 异常；没有改为通过或借给本次源码验收。网络代际用受控事件注入，未实测手机 Wi-Fi 切换蜂窝。

[下载 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.21-gecko/PocketChat-1.5.21-gecko-arm64.apk)：1.5.21 / code47，SHA `709dd0525f7a13deb23cd955078304fcdd82163db68ee6860ca3265039b73937`，原签名 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。[完整公网下载](public-download-verification.json)、[更新源](public-update-feed-verification.json)、[官方 CDN Range/If-Range](public-range-verification.json) 与原签名 APK 一致，支持覆盖安装。环境登录、固定出口和失败拒绝保护保留，没有自动重发或直连回退。

验收使用 Android x86_64 模拟器与合成节点。尚未验证用户 ARM 真机、真实账号、现场冷启动/电量、不同运营商及同 Wi-Fi 的手机电脑对照；既有偶发输入边界不因本次网络改动而宣称修复。未归档证书私钥、签名密钥、API 令牌或大型 SDK/native/APK 文件。
