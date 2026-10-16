# 2.0.5 正式版验证记录

发布日期：2026-10-16（UTC）。用户明确要求“做这个然后发布”。ARM 真机和跨设备分享验收尚未完成，本记录不将模拟器测试视作真机验收。

## 来源与产物

- 应用源码：`06d19fe76183740e5b1cbac3ddf93c11ce38afc8`。
- 冻结 CI 证据提交：`4836f5151bcd636e5c7d2cb5a2a78f6305664c54`。
- 发布产物提交：`83abfa261a1452c5c4bd4b65ddb36f17f22514bc`。
- 包名 `local.pocketchat`，版本 `2.0.5`，versionCode `58`，ARM64。
- 文件：`PocketChat-2.0.5-gecko-arm64.apk`，119098632 字节。
- APK SHA-256：`56c1014c2c2b53f2bd69b74070f32deb12c3aa7f627045d7e50ccae7c349ec27`。
- 原签名证书 SHA-256：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`，可覆盖安装。

## 已完成验证

- [Gecko Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38909241039)：成功。
- [构建、lint 与主机回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38909240956)：成功。
- [正式发布流水线](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38914352562)：成功，重新校验冻结证据、APK 来源及原签名。
- 现有五组发布门槛、15 份实际 Android 回归报告及四份订阅主机报告通过；覆盖输入、阅读、环境、附件、下载、订阅、固定出口、延后应用、模板与资源管理。
- 新增网络分享：42 项 Android/原生检查通过；5 次真实 Android 屏幕点击完成分享入口、复制、文件导入预览、选择环境与取消应用。
- 分享入口、出口、整条线路的格式往返验证；仅提取选定节点，保留必要传输参数。拒绝未知版本、超限/深层输入、递归 YAML、外部文件字段、路由覆盖与身份数据。
- 实际 Mihomo 解析、Android 加密缓存、重复导入复用、原网络和草稿保留、候选配置与失败导入不覆盖旧库检查通过。
- 本地受控线路实际连接：导入入口 → 固定出口 → TLS 测试网站，重新核验出口；两个来源均使用本地缓存，不请求虚构订阅地址。测试流量限定在 loopback。
- 导入 UI 停在“保存并应用”前，并实际点击取消；测试没有替用户应用真实网络配置。
- 公网匿名完整 APK 下载：字节数与 SHA-256 与原签名文件一致；公网 release-manifest 与本地发布清单一致。
- Range / If-Range 两次返回 206，核对偏移 0 与 1024 的各 1024 字节以及稳定强 ETag。
- 自动更新清单指向 versionCode 58，SHA-256 一致；GitHub latest 指向 `v2.0.5-gecko`。

## 本轮测试修正

首次 Android 流水线 `38899133346` 的订阅表单输入被系统拼写建议浮层遮挡，定位焦点超时；原生解析与存储检查已通过。后续测试仅在识别到 `android:id/suggestionWindowContainer` 时用真实返回键关闭浮层，随后仍要求目标输入框取得焦点并核对实际输入值。四项主机检查覆盖焦点、拼写浮层、其他弹窗和重复字段；没有跳过表单检查或通过程序直接填写字段。

第二次流水线 `38904355457` 出现 ADB 安装包读取中断，随后模拟器掉线，分享测试未能启动；该轮未被认定为通过。下一轮在启动模拟器前停止已完成编译的 Gradle daemon，并保存模拟器日志及主机资源快照；完整验收门槛保持不变。

## 范围与限制

首期支持单入口、单 SOCKS5 出口及其组合，通过文件或复制配置分享。不包含订阅地址、多入口池、二维码或在线撤回。接收方需升级到本版，导入后仍需明确选择环境并保存应用；不迁移或清理 ChatGPT 登录和环境存储。

跨手机文件分享、ARM 真机、百度输入法及真实 ChatGPT 账号场景尚未验收。此前快速切换光标后立即输入的间歇性错位仍未修复。受控线路通过不等于真实公网节点速度或跨设备兼容性已验证。

[正式版](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.5-gecko) · [APK 下载](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v2.0.5-gecko/PocketChat-2.0.5-gecko-arm64.apk)
