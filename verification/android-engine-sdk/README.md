# Android 预编译内核 SDK 首轮实测

2026-10-03，选用 Mozilla 官方 GeckoView 发布版 `157.0.20260924084938`。已实际取得、校验、集成并编译；原生 Android 35 模拟器测试通过。**没有替换正式应用内核，没有验证 Google / ChatGPT 真账号登录。**

## 可确认的结果

| 项目 | 结果 | 验证范围 |
| --- | --- | --- |
| 官方 SDK 来源与完整性 | 通过 | 官方 Maven AAR 与官方 SHA256 一致，锁定版本和源码 revision |
| Android APK 构建 | 通过 | JDK 17、Gradle 9.8.0、AGP 9.4.1、编译平台 37.1；完整合并 SDK 清单和依赖 |
| 两环境存储隔离 | 通过 | Cookie、localStorage、IndexedDB、CacheStorage、Service Worker 分别写入、读取及互不共享 |
| 进程重启后持久化 | 通过 | 环境 2 的全部合成数据保留；环境 1 的官方清理操作保持删除结果 |
| 按环境清理 | 通过 | 调用 `StorageController.clearDataForSessionContext`；清理环境 1 不删除环境 2 |
| 固定 SOCKS5 线路 | 通过 | 合成 HTTP 重定向、远程 DNS、WebSocket、专用 worker、Service Worker、1152 bytes 响应读取 |
| 代理故障禁止直连 | 通过 | 停止代理并关闭已有隧道，真实页面加载报错，测试服务器没有收到直连请求 |
| 项目每环境代理 | 未接入 | 代理事件没有区分 Gecko context 的完整元数据，不能将本轮全局 SOCKS 通过当作正式线路通过 |
| Google → ChatGPT 登录 | 未测试 | 没有已连接 ARM64 真机或真实账号测试；本实验包只开放受控站点 |
| 上传、正式下载中心、后台回复 | 未迁移 | 1152 bytes fetch 不代表 Android 下载服务、附件或原项目后台任务已经适配 |

测试在 [CI run 37103341373](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37103341373) 的 KVM Android 35 x86_64 模拟器执行，使用真实 GeckoView SDK 与合成 HTTP / SOCKS 服务，不是浏览器状态模型测试。云环境的完整 Gradle 解析被 Maven Central 出口 IP 限流阻挡；本地软件模拟器也出现系统 UI 无响应，最终通过结果来自上述 CI，不能写成 Android 真机或云端本地全通过。

## 实验产物

源码：`92a0b916b0e48624a119875972e957d296621b23`，分支 `feature/android-engine-probe`。

产物提交：`7c714381d761f119105715f810f167af8b6fdfd9`，分支 `apk/gecko-sdk-probe-20261003`。

[ARM64 实验 APK 公网下载](https://raw.githubusercontent.com/Ararataki-number-one/yuanying-chat/7c714381d761f119105715f810f167af8b6fdfd9/PocketChat-GeckoProbe-0.1.0-arm64-v8a.apk)

- 包名：`local.pocketchat.engineprobe`，版本 `0.1.0-gecko-probe`，独立实验包。
- 文件大小：102,187,163 bytes，约 102 MB / 97.5 MiB。SDK 全 ABI AAR 下载为 241,700,764 bytes；两者都不是 Chromium 完整源码编译所需的工作空间。
- SHA256：`67d41bdcadbbf76a16de861ad6112c23153799ec4598c7d1f55434af496f428b`。
- CI 调试签名，正式包原签名密钥没有上传；不覆盖正式应用或读取其登录和订阅。
- x86_64 APK 108,955,084 bytes，在 CI 安装并执行测试；超出此发布脚本的 Git blob 限制，所以没有放到下载分支。

这个包用于运行 [设备测试脚本](../../engine-probe/tests/run_device.py)，需要 ADB 和受控 loopback 服务。它目前不能作为日常 ChatGPT 浏览器或 Google 登录修复版使用。正式应用保持 1.5.6 和原有 WebView 数据。

GeckoView 采用 MPL-2.0；[对应官方源码](https://hg.mozilla.org/releases/mozilla-release/rev/8eb25af4acf031ab1e06abf1a912275083c820ed) 及许可证见 SDK POM 元数据。本项目没有修改 SDK 原生内核。

## 两项实际发现

1. **环境存储与代理路由是两套机制。** 两个 context 已实测隔离，但代理事件的 `cookieStoreId` 在两个环境都是 `firefox-default`，Service Worker 的 `tabId=-1`。仅按窗口 tabId 选线路不足以覆盖后台请求。正式接入需要验证每环境独立 runtime / profile / 子进程，或取得能传递环境标识的 SDK 路由接口；还要复用已有 Mihomo / SOCKS5 / 固定出口配置。
2. **网页 JS 删除不等于磁盘清理完成。** 早期用网页删除 localStorage 后立即 force-stop，重启出现旧记录。改用官方按 context 清理接口后，删除结果和另一环境的保留均通过。本 SDK 的该接口返回 `void`，本实验通过重载与重启验证效果，没有声称 SDK 提供完成回调。正式删除环境还需要处理清理期间的生命周期。

测试站点通过 SDK 的标准标题事件回传合成结果，只在实验包内生效。它不是 ChatGPT 首页，也没有修改正式 Google / ChatGPT 标题或页面 UI；正式网页观察桥仍需单独迁移验证。用户 Chrome 插件和网络功能开发继续暂停。Gecko 的 Mozilla XPI 能力不代表原生 Chrome CRX 兼容。

## 证据文件

- [官方 SDK 下载与校验](sdk-artifact.json)、[工具链校验](toolchain-receipts.json)、[最终 APK 清单](manifest.json)。
- [当前 CI 步骤状态](ci-build-status.json)、[构建日志](build.txt)、[设备测试日志](native-test.txt)。
- [原生设备结果](device-results.json)、[实际 SOCKS / HTTP 请求](device-route-trace.json)、[SDK 原生事件](device-native-events.txt)。
- [代理 context 源码证据](proxy-context-evidence.json)、[实际事件摘要](proxy-context-runtime-summary.json)。
- [早期 JS 清理重启失败](javascript-clear-restart-failure.json)，保留用于解释官方清理 API 的选择。
- [设备截图](device-screen.png)、[依赖校验元数据](verification-metadata.xml)。

编译和受控测试说明成熟预编译 SDK 可以成为实验起点；每环境正式线路和真机 Google / ChatGPT 登录尚未通过迁移门槛，因此本轮不切换正式浏览器。
