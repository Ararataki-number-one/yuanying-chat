# 1.5.8 手机阅读与浏览器运行验证

正式包 `local.pocketchat`，版本 1.5.8 / code 34。编译与设备验证源码：`ed1cd238652da6e1a3d5e2c49900ffa64845b329`。

[编译与 Android 原生回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37124275948)通过。验证设备为 Android 15 / API 35、x86_64。独立非调试回归包使用受控网络样本；测试 Activity 和 HTTP 例外不进入正式 APK。

## 实际验证

- 完整 release / integration 编译和 Lint Vital 发布检查通过，没有宣称全部 Lint 规则通过。
- 生产请求管理器 18 项 JVM 检查通过，包括旧连接干扰、重复结果、超时、重入与连续 1000 次请求的计时任务释放。
- 生产阅读控制器 38 项 JVM 检查通过，覆盖每环境缩放、旧设置一次换算、实际视口等待、旋转宽度、手势、登录页边界和键盘处理。这里使用宿主模拟对象，不是实际 Android 键盘操作。
- Android 实际执行 29 次受控操作，两个环境分别验证可信触摸打开子窗口、子窗口返回 / 关闭、父窗口返回历史、会话关闭后重新打开与原网页存储保留。
- 被关闭的后台父窗口返回后能恢复。关闭会话使用真实 SDK close / open / 渲染，并注入 `onKill` 契约；没有声称模拟器实际发生系统低内存回收。
- SDK 首次绘制早于慢资源完成。首次绘制可能只包含背景，不代表正文或交互已就绪；停止加载测试先核实当前文档与正文，再确认停止慢资源没有显示错误、文档仍可由桥接读取。
- 原双环境 Cookie / HttpOnly / LocalStorage / IndexedDB / Cache / ServiceWorker、HTTP / SOCKS、远端 DNS、worker、WebSocket、重启、原生清理和封闭初始线路检查继续通过。
- 正式 MainActivity 能承载实际 GeckoView，五个底部入口可见，无 Java 崩溃；`device-screen.png` 是主动关闭受控线路后的外层恢复界面。

## 响应式阅读

Android 实际内核分别验证约 362 / 393 / 432 CSS px 竖屏，以及 736 CSS px 横屏：Firefox 桌面 UA、手机视口、100% 初始缩放、响应式侧栏折叠、接近整行宽度的输入框及未发送内容保留。几何和 UA 结果见 `device-results.json` 的 `responsiveReading`。

`reading-*.png` 是内核实际渲染的受控响应式 HTML，明确标注测试内容；它们不是官方 ChatGPT 在线效果或登录成功截图。公开站点布局仍由真实网站决定。安装到用户手机后需要核对官网显示。

## 正式包

沿用原证书、包名，版本号提高到 34，可覆盖同签名正式版。已确认非调试、无测试 Activity，以及 ZIP 16 KB 对齐。原密钥没有上传。

- APK：`PocketChat-1.5.8-gecko-arm64.apk`
- 字节：`120409329`
- SHA-256：`9b68ab576c3ca2d3d73d00fba1d2ea07928d06ade319cceea6ed41789662b6ed`
- 原签名证书 SHA-256：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`

`apk-verification.json` 把签名 APK 与本次未签名构建哈希绑定；本目录 `manifest.json` 和设备报告绑定准确源码。`public-download-verification.json` 记录匿名公网下载的字节和 SHA-256，与本地原签名 APK 一致。下载：[1.5.8 正式应用 APK（ARM64）](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.8-gecko/PocketChat-1.5.8-gecko-arm64.apk)。

真实 Google / ChatGPT 账号、ARM 真机覆盖安装、真实系统回收、真实订阅完整线路、八环境并发和手机键盘长时间输入仍需设备验收。受控存储保留不等于真实账号登录成功。插件和网络新功能继续暂停。
