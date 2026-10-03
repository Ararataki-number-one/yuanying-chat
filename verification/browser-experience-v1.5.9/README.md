# 1.5.9 缩放、登录记录与页面恢复验证

正式包 `local.pocketchat`，版本 1.5.9 / code 35。编译与设备验证源码：`4e704c63fb7bd8ad3799b41e2bf64f2d89bd28af`。

[编译与 Android 原生回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37135473325)通过。设备为 Android 15 / API 35、x86_64；独立非调试回归包使用生产浏览器代码、两个实际环境进程与受控网络样本。测试 Activity 和 HTTP 例外不进入正式 APK。

## 验证结果

- 完整 release / integration 编译及 Lint Vital 发布检查通过；没有声称全部 Lint 规则通过。
- 67 项主机检查通过：请求生命周期 18 项、阅读控制器 39 项、生产扩展会话 Cookie API 检查 10 项。主机模拟对象不能代替实际浏览器验证。
- Android 实际执行 61 次受控操作；逐项结果见 `device-results.json`，原生事件见 `device-native-events.txt`。
- 实际渲染依次调整为 80% → 60% → 130% → 80%。字体的真实像素尺寸与选择一致，同一文档时间标识及未发送内容保持不变，证明没有重新加载网页。缩小后通过真实 Android 触摸定位输入框，再用 ADB 按正常打字间隔输入，焦点、完整文本及顺序正确。
- 两个独立环境的 AndroidX ProcessLifecycleOwner 均进入 RESUMED。12 次不重新加载的前台环境切换和 Home 后返回均保留模拟会话及草稿。
- 模拟 HttpOnly 会话 Cookie 在应用 force-stop、重启后恢复，两环境值互不混用；退出登录后重启不会恢复已删除 Cookie，另一个环境仍保留登录记录。显式原生清理后，宿主读取 Cookie 时更新私有保存记录，再次重启也不会恢复已清理的会话 Cookie。
- 关闭 SDK 会话后自动重新打开同一环境，恢复 SDK 历史和表单；模拟 Cookie 及未发送文本均保留。这里执行真实 SDK close / open / restoreState / 渲染，并注入 onKill 契约，没有声称实际发生系统低内存回收。
- 四种横竖屏尺寸继续保持桌面浏览器身份、手机宽度响应式布局和原始输入内容。`reading-*.png` 为内核实际渲染的受控页面，明确标记测试内容，不是 ChatGPT 官网截图。
- 可信点击打开子窗口、父子窗口返回与历史、被关闭父窗口恢复、首绘早于慢资源完成，以及主动停止旧加载不误报失败继续通过。
- Cookie / HttpOnly、LocalStorage、IndexedDB、Cache、ServiceWorker、HTTP / SOCKS、远端 DNS、worker、WebSocket、重启、独立清理、系统内核回退及关闭内置扩展后的封闭初始线路继续通过。
- 网络保护启用后，新的唯一标记 HTTP 请求未到达测试服务器且请求失败。此前已获准的后台 ServiceWorker 更新完成不计作新请求泄漏；生产网络实现没有改动。
- 正式 MainActivity 的五个底部入口可见，无 Java 崩溃；`device-screen.png` 是关闭受控线路后的外层恢复界面。

云模拟器的 Pixel Launcher 曾弹出无响应窗口并截获测试点击；回归脚本在返回测试 Activity 前仅停止该模拟器桌面包，并关闭动画。没有屏蔽应用无响应。Home 操作仍实际将应用送入后台。

## 正式安装包

原签名、原包名，版本号提高到 35，可覆盖安装同签名正式版；确认非调试、无测试 Activity，并通过 ZIP 16 KB 对齐。原密钥没有上传。

- APK：`PocketChat-1.5.9-gecko-arm64.apk`
- 字节：`120413425`
- SHA-256：`a6147f97817a9f515bec9765ca82efbe9c661cb76807432f0c78e4ec4e2677ae`
- 原签名证书 SHA-256：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`

`apk-verification.json` 把签名 APK 与本次未签名构建绑定；`manifest.json` 与设备报告绑定准确源码。`public-download-verification.json` 记录匿名公网完整下载的字节和 SHA-256，与本地原签名 APK 一致。

下载：[1.5.9 正式应用 APK（ARM64）](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.9-gecko/PocketChat-1.5.9-gecko-arm64.apk)。

Google / ChatGPT 真实账号、ARM 真机覆盖安装、真实系统回收、真实订阅线路、八环境并发，以及手机键盘长时间输入仍需实际设备验收。可信触摸加 ADB 简单文本输入不等于已验证 ChatGPT 富文本输入、中文输入法、语音或音视频。客户端保存与恢复不能延长服务器登录有效期；网站主动使会话失效时仍需登录。插件和网络新功能继续暂停。
