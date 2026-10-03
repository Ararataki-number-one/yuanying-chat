# 1.5.7 正式应用网页内核更新

原包名 `local.pocketchat`，versionCode 33，保留原签名。此次改动接入正式应用，不再要求用户用另一个实验包连接电脑测试服务。网页继续来自真实网站。

## 使用变化

默认通过官方 Firefox GeckoView 打开原网页，可沿用环境中的手机版 / 电脑版选择。首次需要在新内核登录，原系统 WebView 的登录目录保留。在会话“更多 → 浏览器内核”切换；切换会重新打开当前环境。Firefox 的简洁聊天表现层尚未迁移，点“简洁”会说明并切回原系统内核。原有未完成回复暂时继续使用系统内核，避免中断。

加载失败时提供明确的重试、网络检查和内核选择入口。新版未承诺真实 Google 登录已经成功；Google/ChatGPT 账号登录仍需要手机验收。

## 文件与原因

| 文件 | 修改 |
| --- | --- |
| `GeckoWebView.java`、`GeckoSettings.java` | 以原生 FrameLayout 承载 GeckoView 或系统 WebView，沿用会话调用接口；Firefox 模式不初始化 Chromium。实际网页、导航、文件选择和下载由官方 SDK 处理。设置元数据接口只供旧调用者读取，实际 Firefox 配置走 SDK；忽略内核启动空白页的导航通知，避免误报加载失败。 |
| `GeckoEnvironmentContext.java`、`GeckoEnvironmentServices.java` | 延续每环境独立 Android 进程和浏览器目录，为 SDK 子进程绑定加入环境标识，避免两个环境复用同一浏览器子服务。 |
| `PocketApplication.java` | 恢复 Android Application Context 契约，兼容 AndroidX 原生初始化；Activity/Service 的 ProfileContext 仍负责环境存储隔离。 |
| `assets/gecko/` | 内置路由扩展逐请求调用现有网络守卫和每环境代理，支持 SOCKS 远端 DNS；后台扩展读取该环境下载所需的 Cookie（含 HttpOnly）。路由回调使用可由 SDK 序列化的 JSON 字符串；本地配置在扩展不可用时阻止连接。没有用户扩展安装功能。 |
| `ChatSession.java`、`WebReplyObserver.java` | 浏览器适配层接入原会话生命周期和消息观察；系统分支保留原接口，新内核的桥接位于扩展隔离上下文。 |
| `BrowserPrivacy.java`、`BrowserNetworkGuard.java` | Firefox 使用原生网页模式、跟踪保护与请求路由；避免在 Firefox 进程初始化 Chromium 的 UA、Cookie 或 ServiceWorker 组件。旧系统内核保护继续保留。 |
| `BrowserEngineUi.java`、`EngineRestartActivity.java` | 内核选择保存到当前环境，由独立的原生控制进程重新打开该环境。未完成提问、附件和传输时不打断工作。 |
| `MainActivity.java` | 复用会话外层 UI，原网页下不创建本地 Chromium 阅读器；原生网页返回导航，加载状态可见。 |
| `LoadingUi.java`、`LoginHelpUi.java`、`EnvironmentEditorUi.java` | 增加真实内核信息、启动/加载失败反馈和切换入口，登录帮助区分当前内核。 |
| `WindowHomeActivity.java` | 新环境默认 Firefox，创建电脑版环境时不在管理进程加载 Chromium 做旧检查。系统内核兼容性在打开该环境时处理。 |
| `FileDownloads.java`、`PageMemory.java`、`Attachments.java` | 下载使用当前内核的登录 Cookie，缓存标识区分两个内核，保留原下载、代理和续传管线；文件选择回调读取当前浏览器的真实 URL。 |
| `EnvironmentAudit.java` | Firefox 自检尚未迁移时明确说明并停止发起检测，保留旧报告；不拿系统 WebView 的结果代表新内核。 |
| `AndroidManifest.xml`、`res/xml/network_security.xml` | 更新版本和私有控制 Activity，保留原隔离组件；XML 补显式字段以通过发布 Lint。 |
| Gradle、Wrapper、`build.ps1` | 固定 SDK/AGP/Gradle/Gecko 版本，正确合并官方 SDK 原生库、服务、资源和传递依赖；替换不适用的新内核手工打包入口。 |
| `tests/gecko/`、构建工作流 | 非调试的独立设备回归包与受控网络样本，测试入口不进入发布包。 |
| `tools/sign-apk.py`、`tools/publish-gecko-release.py`、发布工作流 | 原密钥只在本地签名；校验证书、版本、字节哈希和对齐，再把已签名 APK 发布为公网下载。 |
| `third-party/`、构建与验证文档 | 记录官方 SDK 校验和、准确源码 revision、Mozilla 许可、构建方式和验证边界。 |

## 当前边界

没有改动 `NativeNetwork` 网络核心、订阅解析、固定出口或 `ChatService` 后台回复服务源码。浏览器承载和外层接入已有调整，真实网页登录不保证由换内核自动解决。

Firefox 尚未接入旧 Canvas/音频/设备字段保护脚本及旧网页环境自检；UI 的保护详情已经说明。Google 登录、ARM 真机、真实订阅/Mihomo 完整线路、手机横竖屏及实际键盘阅读体验不能用合成样本替代。
