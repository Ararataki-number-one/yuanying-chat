# 1.5.4 环境网页显示预览（原版签名）

版本 1.5.4（versionCode 30），更新日期 2026-10-03。

[下载 APK](https://raw.githubusercontent.com/Ararataki-number-one/yuanying-chat/refs/heads/apk/desktop-environments-preview-20261003/public-downloads/PocketChat-1.5.4-desktop-environments-preview.apk)，49,374,574 字节。

SHA-256：`45c4fda8f8fd6c952c366bb6622ec4b0d485ec079c9a65ef7479388029d7b09c`。

包名 `local.pocketchat`，使用原发布签名，可覆盖原签名版本。此前临时签名包不适用；覆盖后真实账号登录保持仍需手机核验。私钥未公开。

## 使用

- 新建环境 → 基本信息 → 网页显示方式，选择手机版 / 电脑版。
- 已有环境 → 编辑环境 → 浏览器 → 网页显示方式，保存环境后应用。
- 每个环境独立保存，旧环境默认手机版。环境列表仅在辅助信息行提示电脑版，会话顶部不增加按钮。
- 电脑版继续使用真实 ChatGPT WebView，保留简洁 / 原网页逻辑，允许双指缩放。
- 保存前复用原草稿和阅读位置保存能力；回复、连接或其他操作进行中提示等待；草稿保留失败不应用修改。

## 验证

发布和独立测试 APK 均通过编译、原签名、对齐及包版本检查。浏览器策略 23 / 23、视口 DOM 12 / 12、主机 SQLite 迁移 8 / 8，共 43 / 43 项主机检查通过。

本轮未连接真机、未登录真实账号。Android WebView 的实际电脑版布局、缩放、键盘、跨进程配置和登录保持未完成设备验证；原生创建表单用例仅编译，未运行。电脑版仍是 Android WebView。上一轮云模拟器渲染崩溃和恢复耗时失败保留在历史记录中，本轮未重跑或声称解决。

[修改文件及原因](https://github.com/Ararataki-number-one/yuanying-chat/blob/e4a00220c63d25e710bb61d1f1a00487c94347ee/docs/CHANGELOG-v1.5.4.md) · [验证结果与设备清单](https://github.com/Ararataki-number-one/yuanying-chat/blob/e4a00220c63d25e710bb61d1f1a00487c94347ee/verification/environment-browser-display/README.md)

源码提交：`e4a00220c63d25e710bb61d1f1a00487c94347ee`；源码分支：`feature/environment-browser-display`。历史 APK 保留。
