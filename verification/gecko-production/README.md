# 1.5.7 正式应用浏览器验证

本轮接入正式应用 `local.pocketchat`，versionCode 33。源码提交：`9fc8204af0032563c607cadb60d2b56f34add2ad`。

[完整编译与设备回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37115337143)已通过。设备为 Android 15 / API 35、x86_64，1080 × 2400 / 420 dpi；使用非调试独立回归包，受控 HTTP 样本入口不进入正式包。

## 实际检查

| 检查 | 结果与边界 |
| --- | --- |
| 发布与回归编译 | ARM64、x86_64 构建成功；发布所需 Lint Vital 检查通过，详见 `build.txt`。没有将其称为全部 Lint 规则通过。 |
| 两环境存储 | Cookie（含 HttpOnly）、LocalStorage、IndexedDB、Cache、ServiceWorker 分开；两个环境先后读写并互相核对。 |
| 两环境线路 | 环境 1 使用 SOCKS，环境 2 使用 HTTP；验证重定向、代理端域名处理、WebSocket、Dedicated Worker 和 1152 字节受控下载。 |
| 暂停与恢复 | 环境 1 的守卫阻止新导航，其路由候选为关闭端口；环境 2 继续读取。 |
| 持久保存 | 应用进程停止后恢复两个环境；选择系统内核启动，再重新启动 Firefox，原 Firefox 数据仍在。此检查没有模拟点击私有重启 Activity 的全部交互。 |
| 原生清理 | 调用 Gecko 原生清理后环境 1 数据为空，环境 2 不变；没有用网页 JavaScript 代替原生清理。 |
| 扩展不可用 | 禁用内置路由扩展后，受控网页连接失败；验证关闭的初始代理配置有效。 |
| 正式外层界面 | 实际 `MainActivity` 能承载保留的 GeckoView，五个底部入口和原网页模式可见，无 Java 崩溃。首次通知权限在测试手机上预先授予。 |
| 原签名 | 本地签名、原证书、包名、版本号、非调试状态、无测试 Activity 和 ZIP 16 KB 对齐均通过。正式包为 ARM64。 |

`device-results.json` 记录 17 次设备操作及分类结果，`device-route-trace.json` 和 `device-native-events.txt` 保留合成数据证据。每次导航带独立标识，旧页面的结果不会充当新页面的结果。`apk-verification.json` 将已签名 APK 与本次未签名构建的哈希对应起来。

`device-screen.png` 是主动关闭测试线路后的错误反馈界面，用于检查正式外层界面与恢复入口；它不是成功访问 ChatGPT 的截图。编译、模拟器和签名验证不能替代手机上的真实覆盖安装与账号登录。

## 尚未验收

真实 Google / ChatGPT 登录、ARM 真机、真实订阅 / Mihomo 完整链路、八环境同时运行、文件选择及实际下载交互、横竖屏与键盘阅读仍需设备验收。新内核需要首次重新登录；原系统内核的数据保留。Firefox 当前用于原网页，简洁模式会重新打开系统内核；旧指纹脚本和网页自检尚未迁移。

本轮没有修改原网络核心、订阅解析、固定出口及后台回复服务源码。没有把合成页面或本地 HTML 当作官方 ChatGPT 网页，没有加入 Chrome 扩展安装功能。
