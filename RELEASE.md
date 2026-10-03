正式应用 1.5.7，原版签名，versionCode 33。适用于 ARM64 Android 手机，可覆盖同签名正式版，无需卸载。

真实网页改由 Mozilla 官方 GeckoView 加载，沿用原有环境数据和每个环境的网络配置。加载失败时显示重试和内核切换入口。

新内核首次需要重新登录；原系统内核的登录数据保留。可在“会话 → 更多 → 浏览器内核”切回系统内核。Firefox 当前用于原网页，简洁模式会重新打开系统内核；两种内核各自保存登录。原有未完成回复会暂时保留系统内核以避免中断。

Android 15 原生回归已验证两个同时运行的环境、Cookie（含 HttpOnly）/LocalStorage/IndexedDB/Cache/ServiceWorker 隔离、独立 HTTP/SOCKS 代理、远端 DNS、Worker/WebSocket、重启恢复、原生清理和系统内核切换。

真实 Google/ChatGPT 登录与 ARM 手机尚待用户设备验证，本发布不承诺已经解除 Google 的浏览器登录限制。没有加入 Chrome 扩展安装功能。新内核的保护功能覆盖跟踪保护及 WebRTC 禁用；旧 WebView 指纹脚本和自检未移植。
