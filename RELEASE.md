# PocketChat 2.1.13（115）

- Gecko 随主安装包提供，未设置内核的环境默认使用 Gecko。启动、切换环境和打开网页链接时，应用按目标环境保存的内核选择打开网页。
- Android 10 及以上可在环境的浏览器设置中选择下载安装独立 Chromium 组件。组件沿用当前环境的下载线路。应用会核对版本、架构、签名和摘要，再由 Android 追加安装。
- Chromium 按环境使用已设置的系统网络、内置线路、固定代理或强制 VPN。环境线路失效时，Chromium 会停止当前连接。强制 VPN 的路由核验需要 Android 13 或更新版本。每个环境使用独立的登录和网站数据目录。旧 WebView 登录资料保留在原目录。
- 调整内核前，进行中的网页或文件操作会提示先完成。原生网络、设置和已保存文件可单独打开。Gecko 下载续传会检查响应范围和正文边界。
- 环境批量收藏和分组操作会核对环境身份。更新时继续校验包名、版本、摘要和原签名。

Chromium 组件使用 Cefrium 0.21.0（LGPL-3.0-or-later），包含原始第三方声明。对应材料见 [上游源码](https://codeberg.org/cefrium/cef-android/archive/v0.21.0.tar.gz) 和 [许可声明](https://codeberg.org/cefrium/cef-android/releases/download/v0.21.0/cefrium-sdk-0.21.0-NOTICE.txt)。
