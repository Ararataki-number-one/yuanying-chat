# 1.5.15 图片选择与手动测速验证

源码：`d387350a496c5b93d6b05c02ecf84fc8476ee8de`。逐文件说明见 [修改说明](../../docs/CHANGELOG-v1.5.15.md)。

[完整构建与 Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37205631447)通过。正式 ARM64 APK、独立 x86_64 测试包和 Lint Vital 均完成构建；105 项既有主机检查、67 项真实 Android / Mihomo 网络检查、78 次浏览器操作，以及 30 张原生界面与 3 张网络模式截图对应的界面验证通过。

## 新增检查

- 应用等待回复时，真实 Firefox 电脑版文件输入调用生产 `Attachments.chrome()`，文件选择请求未被等待状态拒绝。
- 选择请求使用图片 MIME 和多选设置；无扩展名、仅提供内容流的 PNG 在交付浏览器后具有 `image/png` 类型，真实解码为 4 × 3 像素，并被受控 HTTP multipart 接收。
- 选择过程保持等待回复对象，不创建虚假的原生附件上传记录。
- 回复忙碌时手动完整线路测速成功，保留入口、固定出口 IP、当前连接代号和运行中的代理内核。自动后台维护继续避让，取消与连接恢复回归保持。
- 既有登录存储隔离、前后台、进程恢复、缩放、CSV / Blob 下载、延后应用配置、环境删除与自动更新回归继续通过。

[完整产物与原生截图](https://github.com/Ararataki-number-one/yuanying-chat/tree/a5717756e539ecb21cbacaf0507b73d2581a86bb)。详见 [浏览器报告](device-results.json)、[网络报告](network-performance-results.json)、[界面报告](ui-visual-results.json)、[构建日志](build.log)。

## 公网与原签名

[下载正式 1.5.15 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.15-gecko/PocketChat-1.5.15-gecko-arm64.apk)，可以覆盖原签名版本。

- 版本：1.5.15 / code 41；大小：120462577 字节。
- SHA-256：`ed3878a34d68d748af8aeadddc24b76fe72c0074b3387888a3c59697d7fb78a6`。
- 原证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。
- [APK 校验](apk-verification.json)：非调试、无测试组件，16 KB ZIP 对齐。
- [发布任务](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37206523399)通过；[匿名完整下载](public-download-verification.json)与[自动更新源](public-update-feed-verification.json)核验版本、源码、哈希和原证书一致。

## 范围

图片测试运行真实 Gecko 浏览器与生产文件选择处理。测试只适配受控页面来源，并注入系统选择结果；未手动操作 DocumentsUI，也未使用真实 ChatGPT 账号或连接用户真机。PNG 确实通过浏览器上传到受控服务器；这不等同于真实账号端到端验收。正式 APK 没有测试页面、测试提供方或来源适配。
