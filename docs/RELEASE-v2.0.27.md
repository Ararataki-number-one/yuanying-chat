# 2.0.27：移动公开字段一致性

versionCode 80，扩展版本 2.0.27.80。正式版已发布，原证书可覆盖升级：[下载 ARM64 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v2.0.27-gecko/PocketChat-2.0.27-gecko-arm64.apk)。本次只更新 2.0.27，后续版本继续逐版推进。

- 沿用已有屏幕、DPR、触摸和旋转检查，新增当前网页与同源 iframe／Dedicated Worker 的 `platform`、`appVersion` 对照。
- 字段缺失、类型错误、过长、含控制字符、主页面未采集或报告过期时标为未覆盖；不把隔离扩展世界的值冒充网页结果。
- 显示手机版／电脑版的显示请求，分别解释网页公开字段、HTTP 请求身份和实际设备身份。

保持单 GeckoView、ChatGPT 原网页及原有环境隔离与固定出口。本版不覆盖网页属性，不增加联网、后台定时采集或任意手机型号伪装；新增字段用于同次观测内的比较，没有扩大跨重启历史基线，也不包含 2.0.28—2.0.30。

## 本版验证

源码 `ec0cfbe43af2a9fc2bd748229e7cdca1081e7806`，源码树 `9d76122eb2a9ce7e1eba5e301305cba991a048cc`。正式受控运行 [40669216626/1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40669216626) 的 11 个任务全部通过，十项原发布门禁各执行一次，没有重跑或混用后续版本结果。完整 Release／Integration 编译、派生 Gecko SDK 来源及受控 Android 回归均通过。

本版移动公开字段主机检查 39 项、身份控制器主机检查 95 项，均分别使用桌面与 Android JSON 实现通过。已有原生保护、输入、文件、环境、网络与发布检查继续保留；受控数据和主机检查不代替真实设备验收。

## 正式发布与独立核验

[发布运行 40675359509/1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40675359509) 全步骤成功。随后独立匿名下载整个公开 APK，并核对包名、80版本号、ARM64、原证书、SDK 来源、16KB 对齐、测试组件排除和更新入口；标签通过连接的 GitHub API 另行核对，精确指向上述源码。

- APK：`PocketChat-2.0.27-gecko-arm64.apk`，119324325 字节。
- SHA256：`8e7b8fd0e60a5af8c61da3d0d44a84708fb2fa32515e1624eef217ae317825ac`。
- 原证书 SHA256：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。

真实手机、ChatGPT 官网、百度输入法界面与实际保护效果仍未验收。网页与 Worker 公开字段一致不代表它们的 HTTP UA／请求头一致；本版没有据此宣称真实设备身份已统一、手机提速或真实代理延迟改善。用户发布授权也不代替真机验收。
