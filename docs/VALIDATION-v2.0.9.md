# 2.0.9 正式版验证记录

发布日期：2026-10-17（UTC）。按用户“先做这个，然后发布优化后的下一版本”的明确指令发布；这是发布授权，不是 ARM 手机验收记录。

## 源码与安装包

- 应用与发布工具源码：`1c89216078a22c7a6abed4dee838705014195467`。
- 冻结 Android 构建和验证产物：`948545d92bc7b3829df6e334053eccf4b44d35ef`。
- 正式发布产物：`9d468b90bafbe6f107173cf89832a3e631379d83`。
- 包名 `local.pocketchat`，版本 `2.0.9`，versionCode `62`，ARM64。
- 文件 `PocketChat-2.0.9-gecko-arm64.apk`，119119240 字节。
- APK SHA-256：`16b643d0a5613c8a6fa8c375d67bd4c9c28d429002e37db9709be319f965ba66`。
- 原签名证书 SHA-256：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`，可覆盖安装原签名应用。

## 已通过

- [构建、lint 与主机回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/39030701230)。
- [实际 Android 模拟器回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/39030701231)。
- [网络内核独立重建与原生测试](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/39030701313)。
- [正式发布工作流](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/39033768318)。
- 五组发布门槛、15 份 Android 报告和四份订阅主机报告通过；核对源码、构建身份、原签名与实际 APK 字节。
- 上传、下载、恢复、环境隔离、输入、日夜模式、网络分享、反馈和连接池的既有受控回归继续执行。
- 新增真实代理探测的首次建链、TLS、首字节分项检查；未观测 DNS 明确为 -1。
- Gecko 双 SOCKS/H2：首组在认证后停顿 9 秒仍使用原备用 socket；有限寿命约 30 秒，过期后关闭且不提前访问目标。
- 三组受控 Gecko 请求的认证等待节省：[359, 325, 366] ms。第一组含 9 秒停顿，其余是既有即时复用场景；不是三组用户公网测量。
- 公网完整下载 SHA/大小与本地签名包一致；发布清单一致。
- 两次 HTTP Range 返回 206，If-Range 使用同一强 ETag，字节与签名包一致。
- 更新 feed 已指向 2.0.9 / code 62，GitHub latest 正确。

## 性能与未验证范围

本机受控原生对照：9 秒阅读停顿后，旧 8 秒寿命策略 245.95 ms，新 30 秒策略 61.59 ms，减少 184.35 ms。每个模拟握手阶段设置 60 ms，两种策略各测一次。该结果验证减少重复握手的机制，不等于公网线路 RTT 的改善幅度。独立 CI 重建运行的相同受控场景为 242.33 → 60.71 ms，方向一致；同样不是用户公网测量。

用户确认同一 Wi-Fi、未同时运行其他 VPN；尚未拿到 Clash 的具体测试 URL、其完整链路样本和手机新版诊断。没有新增 ARM 真机、真实 ChatGPT 账号或用户公网 A/B 验收，不能声称 400 ms 已降到 200 ms。远端 DNS 无法从客户端独立计时，仍包含在代理建链中。

实现、检测口径及同链路对照步骤见 [网络对照说明](NETWORK-COMPARISON-v2.0.9.md)。

[正式 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v2.0.9-gecko/PocketChat-2.0.9-gecko-arm64.apk) · [发布页](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.9-gecko)
