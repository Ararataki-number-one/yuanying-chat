# 1.5.11 应用更新验证

源码：`7a90460726883f574237dcb0b50bb5cd32946a07`。正式包：`local.pocketchat`，1.5.11 / code 37。

[完整 release / integration 编译、Lint Vital 与 Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37176251636)通过。原有 67 项主机检查和新增 23 项更新检查通过；Android 15 / API 35、x86_64 实际执行 68 次受控操作。

新增验证使用真实 Android DownloadManager 下载合成升级 APK，调用生产更新管理器执行流式大小/哈希/包名/版本/证书检查；正确文件进入 ready。内容改动、不同签名和用户取消均不获得安装 URI。读取私有提供者得到正确 APK，写入和目录穿越被拒绝。更新页展示实际版本与偏好；可信屏幕点击“安装更新”触发再次核验，进入 Android 系统覆盖安装确认界面。测试取消确认，没有安装合成替换包。

原有真实浏览器隔离、HTTP/SOCKS 线路、上传/下载、会话恢复、退出登录、横竖屏、60%～130% 缩放、后台返回和网页恢复等回归继续通过。逐项证据见 `device-results.json`、`device-native-events.txt` 和 UI 截图。

原签名 APK：`PocketChat-1.5.11-gecko-arm64.apk`，120433905 字节，SHA-256：`8f4f7997e389449d6dd95d4660467bb75f1381d36c7f700c7bffd65b66bf8836`。证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。非调试、无测试组件、16 KB ZIP 对齐。公网匿名完整下载通过，正式更新源版本/字节数/哈希与公开 APK 一致。

[下载 1.5.11 正式 APK（ARM64）](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.11-gecko/PocketChat-1.5.11-gecko-arm64.apk)。

限制：测试升级包为合成数据；ARM 真机安装和各厂商后台策略仍需真机复核。未使用真实 Google / ChatGPT 账号。定时检查会受到 Android 调度限制；应用不承诺静默安装或延长网站登录有效期。
