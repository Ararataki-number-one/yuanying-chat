# 2.0.4 正式版验证记录

发布日期：2026-10-16（UTC）。用户明确要求“发布正式版”。本记录不替代尚未完成的 ARM 真机验收。

## 来源与产物

- 应用源码：`745062369a19875f8bff7bf9fb98a16f8372c23f`。
- 冻结 CI 证据提交：`3faea9e5f224c190d8b089fb8e42f276d4832072`。
- 发布产物提交：`0e86154f4e679f6b7f08e142759f9fc1b7920f68`。
- 包名 `local.pocketchat`，版本 `2.0.4`，versionCode `57`，ARM64。
- 文件：`PocketChat-2.0.4-gecko-arm64.apk`，119082248 字节。
- APK SHA-256：`ca3b474060d35f55713ca0279ad5cb189c04d5e1869fbba11dfa333b600d54da`。
- 沿用原签名，证书 SHA-256：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。

## 已完成验证

- [Gecko Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38867294939)：成功。
- [构建、lint 与主机回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38867294955)：成功。
- [正式发布流水线](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38871875680)：成功，重新校验冻结测试证据、APK 来源及签名后发布。
- Android 检查：性能 155 项、输入光标兼容 129 项、网络性能 156 项、安静通知 42 项、更新路径 32 项通过；环境、附件、下载、订阅、固定出口、延后应用及配置模板相关回归通过。
- 实际 Android 点击验证：360dp 宽度、字体比例 1 和 2 下，出口密码默认显示，隐藏再显示后值不变。使用合成测试凭据。
- 紧凑顶部栏三个布局回归通过；“对话已改变”状态隐藏且不可点击，真实发送失败状态仍显示并可操作。
- 发布后匿名完整下载校验：字节数及 SHA-256 与签名 APK 一致，公网 release-manifest 与本地发布清单一致。
- 两次 Range / If-Range 请求返回 206，分别验证偏移 0 和 1024 的 1024 字节内容及稳定强 ETag。
- `app-updates/latest.json` 指向 2.0.4，APK SHA-256 一致；GitHub latest 指向 `v2.0.4-gecko`。

## 验证范围与遗留问题

本次输入回归通过不等于已解决此前快速切换光标后立即输入的间歇性错位问题；该问题仍记为未修复。ARM 真机、百度输入法及真实账号场景尚未验收。入口、出口和整条线路分享只有方案，本版未实现。

[正式版](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.4-gecko) · [APK 下载](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v2.0.4-gecko/PocketChat-2.0.4-gecko-arm64.apk)
