# 1.5.6 电脑版阅读优化（原版签名）

版本 1.5.6（versionCode 32），更新日期 2026-10-03。

[下载 APK](https://raw.githubusercontent.com/Ararataki-number-one/yuanying-chat/refs/heads/apk/desktop-reading-20261003/public-downloads/PocketChat-1.5.6-desktop-reading.apk)，49,382,766 字节（约 49.4 MB）。

SHA-256：`54fbfbdf2fc121d93c697ad4127719933e4d8edd285fbb97d4b28e5c3a656bb8`。

包名 `local.pocketchat`，使用原发布证书，可覆盖原签名版本；真实设备覆盖与登录保持仍需手机验证。签名私钥没有公开。此前临时签名包不适用。

## 阅读优化

- 电脑版按实际可用宽度适应屏幕，各环境独立保存双指缩放；重新加载和重开恢复，横竖屏按新宽度重算。
- 更多菜单新增居中“网页缩放”，微调或适应屏幕，不增加常驻面板、不刷新网页。
- 键盘弹出时原网页会话临时收起底部导航，关闭后恢复；保留安全区，输入自动放大不覆盖用户选择。
- 原网页代码、长回复、草稿、模型和消息结构保留；没有替换 ChatGPT 主页或输入框。

## 登录与内核评估

这版仍使用 Android WebView，**没有解除 Google 登录限制，也没有替换内核**。用户要求保留独立登录和各环境代理，已完成替换内嵌内核的源码评估；优先验证成熟 Android 预编译 SDK。Roxy 的 Windows/macOS 运行包体与 Chromium 源码编译空间是不同概念，电脑内核不能直接放入 Android APK。网络和用户插件功能开发保持暂停。

## 验证

28 项实际控制器 host doubles、13 项输入脚本 DOM、9 项桌面 Chromium 离线布局、12 项 viewport、23 项显示策略、36 项设置／登录策略及 17 项 Google 拒绝检测，共 138 / 138 项已执行主机与桌面浏览器检查通过。发布和独立测试 APK 编译、原签名、对齐和版本通过，测试组件与 HTML 不进入发布包。

原生阅读用例仅编译，没有连接设备、运行 Android 阅读测试或登录真实账号。桌面 Chromium 缩小 viewport 不等于 Android 软键盘；真机双指、横竖屏、输入、代码滚动和覆盖仍需核验。

[逐文件修改说明](https://github.com/Ararataki-number-one/yuanying-chat/blob/94a7de7d9a9208484bdbcd1bf0408b8e8648b639/docs/CHANGELOG-v1.5.6.md) · [验证记录](https://github.com/Ararataki-number-one/yuanying-chat/blob/94a7de7d9a9208484bdbcd1bf0408b8e8648b639/verification/desktop-reading/README.md) · [内核迁移评估](https://github.com/Ararataki-number-one/yuanying-chat/blob/94a7de7d9a9208484bdbcd1bf0408b8e8648b639/docs/BROWSER-ENGINE-MIGRATION.md)

源码提交：`94a7de7d9a9208484bdbcd1bf0408b8e8648b639`；源码分支：`feature/desktop-reading`。历史 APK 保留。
