# 2.0.28（81）

本版完善本地双报告的人工检查进度，并修正手动重载的回复确认边界。

- 显示已记录、未测试、异常与不适用项目；进度表示记录情况，不是保护得分。
- 人工结果菜单显示当前值，编辑时预选已有记录，未操作项目保持“未测试”。
- 保留记录时间；替换报告后重置对应人工结果。打开菜单时合并同一报告的重复读取，点击项目仍读取最新状态。
- 修复当前聊天首次被观察为正在生成回复时，手动重载确认可能遗漏的问题，避免未经确认中断回复。

保持单 GeckoView、ChatGPT 原网页、独立环境和固定出口。本地报告操作不会自动切换模板、刷新聊天或发送消息。

本版已通过[完整受控 Android／Gecko 验收](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40824390290)：11 个任务、原始 10 项发布验证，以及 9 个全新模拟器的启动隔离与网络回读；三组独立输入流程、文件、线路分享和主题检查均通过。

原签名 ARM64 安装包可覆盖升级。真实手机上的输入法、附件、官网使用与保护效果仍需同一设备验收，受控结果不代表手机提速或全部指纹保护效果已验证。

## 发布验证

- APK 源码：`96c0667cbe65e32f6f3b46769ad8f161816a6760`；版本 2.0.28／81，包名 `local.pocketchat`。
- 原签名证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。
- [正式 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v2.0.28-gecko/PocketChat-2.0.28-gecko-arm64.apk)：119,324,325 B，SHA256 `9e92cf76fe2c56a62aa3cb8197fbd56823ad124a7c31a05895cae3d86682d888`。
- [构建与完整验收](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40824390290)与[正式发布](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40830449311)成功。匿名下载的完整 APK、原证书、16 KiB 对齐、源码／SDK、更新入口及标签均已独立核验。
- 真实 ARM 手机覆盖安装、官网登录及保护效果未测试；发布授权不代表真机验收。
