# 1.5.5 · 浏览器设置保存与登录提示修复

用户在电脑版 Google 登录页遇到“此浏览器或应用可能不安全”，同时修改网页显示或隐私等级时被“当前有未完成操作”挡住。本轮暂停插件和网络功能开发，仅处理这两个现有问题的状态与交互。

## 浏览器设置无法保存

1.5.4 将导航、连接、自动重连计时和缓存中的网页 busy 一律作为保存阻塞条件。新的判定区分用户任务和可替换的加载过程：提问未确认、发送、网页操作、下载、上传以及当前网页真实回复仍会阻止修改，并说明具体原因；普通加载、连接和自动恢复等待可在保存时被替换。

保存按钮不再先被旧 busy 缓存挡住，而是复用现有只读驱动检查当前网页。忙碌记录绑定当前页面和导航代次，上一页面或上一代的记录不再影响新页面。检查后继续保留草稿和阅读位置，完成后才应用配置。切换过程中令旧导航、恢复和连接回调失效，防止它们用旧设置覆盖新结果；继续使用同一个 WebView。

任务确实仍在执行时不强制清空 pending、停止回复或丢弃上传，也不把“保存环境”变成解除等待操作。

## Google 登录提示

已知身份提供方的正常登录跳转和 HTTP 4xx 登录页面进入等待登录状态，停止无用的恢复计时，不再写入“登录未完成”作为网络故障。真正的网络错误和服务端 5xx 保留原错误处理。网页同步不对身份提供方页面运行 ChatGPT 驱动。

Google 页面检测只读取明确的浏览器拒绝文案，返回一个布尔值；不采集账号字段、密码、Cookie 或 OAuth 跳转参数，不修改 Google 页面。检测到拒绝后提供一次居中登录帮助；Google 页面更多菜单也可打开帮助。可返回真实 ChatGPT 选择该账号已有的其他方式，或在系统浏览器使用 ChatGPT。

**这没有解除 Google 的登录限制。** 电脑版仍是 Android WebView。Google 拒绝应用内浏览器时，不能保证靠 UA、保护等级或版式设置修好；本轮没有使用伪装内核、复制浏览器 Cookie 或绕过身份提供方限制的方案。系统浏览器的登录不会同步回应用，应用专用代理也不作用于外部浏览器。用户尚未比较同环境的手机版登录，本轮未取得错误 URL 或真实账号复现，不能把所有原因定为电脑版设置。

## 修改文件

| 文件 | 改动与原因 |
| --- | --- |
| `app/src/main/java/local/pocketchat/BrowserSettingsPolicy.java` | 集中实际任务原因和缓存状态的页面／导航绑定 |
| `app/src/main/java/local/pocketchat/BrowserDisplay.java` | 导航、连接、恢复计时不再单独阻止设置保存 |
| `app/src/main/java/local/pocketchat/EnvironmentEditorUi.java` | 保存前新鲜检查当前网页；保留草稿后走统一设置应用入口；具体说明阻塞任务 |
| `app/src/main/java/local/pocketchat/ChatSession.java` | 设置应用令旧回调失效；登录等待与网络故障区分；防止过期页面完成事件影响新导航 |
| `app/src/main/java/local/pocketchat/LoginPagePolicy.java` | 精确匹配 HTTPS 身份提供方域名和只读 Google 文案检测 |
| `app/src/main/java/local/pocketchat/LoginHelpUi.java` | 限于 Google 登录问题的居中帮助和真实入口，明确外部浏览器会话与网络边界 |
| `app/src/main/java/local/pocketchat/MainActivity.java` | 当前拒绝页展示一次帮助，Google 页更多菜单添加上下文入口 |
| `tests/BrowserDisplayPolicyTest.java` | 更新 guard 回归，真实任务与网页回复仍阻塞，瞬时状态允许替换 |
| `tests/LoginSettingsPolicyTest.java` | 36 项实际任务、旧状态及身份域名策略检查 |
| `tests/login-page-detection.cjs` | 17 项拒绝检测、正常／密码错误不误判、可信域名、子框架与页面字段不变检查 |
| `tests/BrowserSettingsRegressionActivity.java` | 实际保存流程的原生回归用例，仅使用拦截夹具；本轮编译但未运行 |
| `app/src/main/AndroidManifest.xml`、`app/src/main/java/local/pocketchat/AppHub.java`、`build.ps1` | 版本 1.5.5 / 31，原生用例仅注册到独立测试包 |
| `README.md`、`docs/BUILD.md`、本文件及 `verification/browser-settings-login/` | 下载入口、修改说明、构建输入及验证结果 |

## 验证范围

发布和独立测试 APK 编译、签名、对齐与包版本核对通过。主机检查 23 + 36 + 17 = 76 项通过；原生保存流程测试仅完成编译。本轮未连接真机或真实账号，Google 登录成功、Android 实际保存流程及覆盖安装后登录保持均未验证。

原版签名用于发布包，版本号递增；私钥没有进入源码或下载附件。网络连接实现、环境隔离和后台回复服务没有新增功能；已有 WebView、Cookie 和登录目录保留。验证材料见 [浏览器设置与登录提示](../verification/browser-settings-login/README.md)。
