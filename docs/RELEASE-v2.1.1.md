# 2.1.1 · 两核网址切换与独立指纹配置

版本号 `2.1.1`，版本代码 `103`。本文件记录实现范围；正式安装包及发布状态以 GitHub Release 为准。

## 两个内核都能打开其他网站

Gecko 增加原生地址／搜索入口与主页按钮，可打开公共 HTTP、HTTPS 网站。Chromium 保留多标签和地址栏。默认网站仍为 `https://chatgpt.com/`，环境设置中的首页对两个内核生效。两核分别保存登录和 Cookie。

Gecko 的普通网站位置与 ChatGPT 会话位置分别保存。在其他网站不注入 ChatGPT 会话、附件、回复检测或草稿操作脚本；导航后的旧异步回调不能把这些操作带入新网站。现有 Gecko 原生隐私模板仍然生效。

## Chromium 独立指纹配置

每个环境单独保存 Chromium 的显示模式、保护模式与稳定随机种子。配置用 Android Keystore 加密，并校验环境身份、配置版本和当前运行代际。新环境不会继承已删除环境的指纹配置，重启或换页不能把历史确认显示为当前确认。

在网页加载之前配置原生 UA／UA-CH，使用当前 WebView 提供者的实际 Chromium 版本。保护模式要求运行时支持 UA 元数据和文档开始脚本；缺少能力时阻止按该配置加载，并显示原因。

可选的文档保护包括二维 Canvas 图像读出／导出、WebGL 调试显卡标识、音频 `copyFromChannel` 复制读出和页面 WebRTC 连接构造器。支持的框架也在文档开始阶段应用脚本。保护种子在同一环境、同一来源保持稳定，可显式更换；保存配置或更换种子会先提示重新加载所有 Chromium 标签页。

原生设置回读与当前页面自检分别显示。它们只确认对应字段和当前运行，不代表完整指纹验证通过。

## 已知范围

Chromium 使用 Android System WebView。Worker、Service Worker、OffscreenCanvas、AudioWorklet、WebGL `readPixels`、实时音频缓冲、独立时区、字体、硬件、系统语言、TLS 和 HTTP/2 指纹未覆盖。电脑版不会把 Android 变成桌面操作系统。页面 WebRTC 限制不覆盖 Worker，HTTP 代理不能代替设备 VPN。

Gecko 使用现有原生保护链路，其支持范围与确认记录在 Gecko 设置和自检中单独查看。不同内核的保护范围不相同。

验证结果随同源构建报告提供；不以主机适配器或桌面 Chromium 的结果代替 Android 验收。
