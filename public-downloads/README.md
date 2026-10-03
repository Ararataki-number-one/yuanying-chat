# 1.5.5 浏览器设置与登录提示修复（原版签名）

版本 1.5.5（versionCode 31），更新日期 2026-10-03。

[下载 APK](https://raw.githubusercontent.com/Ararataki-number-one/yuanying-chat/refs/heads/apk/browser-settings-login-fix-20261003/public-downloads/PocketChat-1.5.5-browser-settings-login-fix.apk)，49,378,670 字节。

SHA-256：`471b8547a6f01297fa4bc11641d7450fc3f41df9abaaa0c0dff959bd36d2b4fd`。

包名 `local.pocketchat`，使用原发布证书，可覆盖原签名版本。此前临时签名包不适用；真实账号覆盖后登录保持仍需手机验证。私钥没有公开。

## 修复内容

- 网页加载、连接和等待自动重连不再单独阻止保存显示方式／保护等级；保存前重新读取当前网页，旧页面和旧导航的 busy 不再卡住表单。
- 保留真实提问、发送、回复、上传、下载和网页操作的保护，说明具体阻塞原因；不自动解除等待或丢弃任务。
- 草稿与阅读位置保留后才应用设置，旧恢复和连接回调失效，继续使用同一个真实 WebView。
- 登录页进入等待登录状态，不再把正常登录或身份提供方 HTTP 4xx 当成网络失败；真正网络错误和服务端 5xx 保留。
- Google 明确拒绝浏览器时提供居中登录帮助及真实 ChatGPT／系统浏览器入口。网络和插件功能开发暂停。

## Google 登录限制

这没有解除 Google 对应用内 WebView 的登录限制。电脑版仍是 Android WebView；Google 登录成功没有验证。系统浏览器的登录不会自动同步回本应用，也不使用当前环境的应用专用代理。没有伪装内核、复制 Cookie 或替换官方登录表单。

## 验证

发布和独立测试 APK 的编译、签名、对齐与包版本通过；23 项显示策略、36 项设置／登录策略、17 项 DOM 检测，共 76 / 76 项主机检查通过。原生保存流程用例只编译，未执行。没有连接真机或登录真实账号。上一轮云模拟器 WebView 渲染崩溃和恢复耗时失败未重跑或声称修复。

[逐文件修改说明](https://github.com/Ararataki-number-one/yuanying-chat/blob/613b54a4276a4d1d7899e62305d05cfcbb247854/docs/CHANGELOG-v1.5.5.md) · [验证与设备核验](https://github.com/Ararataki-number-one/yuanying-chat/blob/613b54a4276a4d1d7899e62305d05cfcbb247854/verification/browser-settings-login/README.md)

源码提交：`613b54a4276a4d1d7899e62305d05cfcbb247854`；源码分支：`fix/browser-settings-login`。历史 APK 保留。
