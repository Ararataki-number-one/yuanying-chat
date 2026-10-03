# 1.5.6 · 电脑版阅读优化

版本号 1.5.6，versionCode 32，继续使用用户提供的原发布签名。

电脑版默认按 WebView 实际可用宽度适应屏幕。双指缩放按环境保存，重新加载或回到环境时恢复；横竖屏切换按新的宽度重算。100% 表示适应屏幕的倍率，放大后可以横向移动。“更多 → 网页缩放”可微调或恢复适应屏幕，不增加常驻工具条，也不刷新网页。

键盘弹出时，原网页会话临时收起底部导航，关闭键盘后恢复。Android 30+ 使用状态栏、刘海、导航栏和 IME 安全区的合并 inset；旧版继续使用 adjustResize / fitsSystemWindows。高度变化不修改用户倍率；键盘或输入框自动放大不计作用户选择。聚焦输入被遮挡时使用原网页的最近滚动，不修改网页结构、文字、字体或输入值。阅读长回复时不自动移到最下方。

代码块与长回复使用官方网页已有渲染和滚动，未加入替代消息界面、CSS 或本地 HTML。测试 HTML 仅在独立测试 APK 中作为离线样本，发布包不包含它们。

## 修改文件

| 文件 | 用途 |
| --- | --- |
| `app/src/main/java/local/pocketchat/BrowserReadingPolicy.java` | 可用宽度、显示密度与倍率换算；可信 ChatGPT 地址与只调整滚动的输入可见性脚本 |
| `app/src/main/java/local/pocketchat/BrowserReading.java` | 复用同一 WebView，监听真实双指缩放、页面与布局；环境私有倍率存储，横竖屏恢复，阻止旧手势回调覆盖新选择 |
| `app/src/main/java/local/pocketchat/BrowserReadingUi.java` | 居中缩放弹窗，微调、适应屏幕与完成；作用于当前环境，不重载网页 |
| `app/src/main/java/local/pocketchat/BrowserPrivacy.java` | 保留原桌面 UA / viewport，把初始缩放交给阅读控制器；手机版不应用电脑版倍率 |
| `app/src/main/java/local/pocketchat/ChatSession.java` | 增加阅读控制器并转发页面、缩放事件；原网络与任务实现保留 |
| `app/src/main/java/local/pocketchat/MainActivity.java` | 条件显示缩放入口，转发缩放与键盘状态，暂停时取消输入可见性检查 |
| `app/src/main/java/local/pocketchat/ReferenceUi.java` | 为会话提供 IME 可见性回调，原有调用者不改变接口；正确合并安全区 |
| `app/src/main/java/local/pocketchat/AppHub.java` | 仅在原网页会话且键盘可见时收起导航及分隔线；恢复后仍是五个导航；更新关于信息 |
| `app/src/main/AndroidManifest.xml`、`build.ps1` | 递增版本；阅读测试组件及 fixture 仅注册／打包到独立测试包 |
| `tests/browser-reading-host/` | 使用最小 host doubles 执行实际阅读控制器，验证倍率、存储、事件和过期回调；不冒充 Android 运行时 |
| `tests/browser-reading-focus.cjs` | 实际输入可见性脚本的 DOM 守卫、无内容改写及登录页不注入检查 |
| `tests/browser-reading-chromium.cjs`、`tests/fixture-desktop-reading.html` | 桌面 Chromium 真实布局检查，覆盖手机宽度、横屏、缩小可用高度、代码与长回复；离线样本，不是官方账号回归 |
| `tests/BrowserReadingRegressionActivity.java`、`tests/ContinuityFixtureActivity.java` | 独立 Android 样本与现有样本的缩放事件转发；本次仅编译，未在设备运行 |
| `README.md`、`docs/BUILD.md`、本文、`verification/desktop-reading/` | 下载、构建、逐文件说明、输入哈希与验证结果 |
| `docs/BROWSER-ENGINE-MIGRATION.md`、`verification/browser-engine-migration/` | 用户追加的内嵌内核源码评估和隔离／网络／登录迁移门槛，没有正式替换内核 |

## 验证与限制

主机控制器、DOM 与桌面 Chromium 检查通过；发布包与独立测试包编译、签名、对齐和版本检查通过。真机双指缩放、软键盘、横竖屏、覆盖更新和真实账号仍需设备核验。具体数量与范围见 [验证记录](../verification/desktop-reading/README.md)。

用户要求保留独立环境和网络配置，已完成 [替换内嵌浏览器内核的评估](BROWSER-ENGINE-MIGRATION.md)。现有电脑版仍是 Android WebView；这次阅读优化没有解除 Google 登录限制。网络和用户插件开发保持暂停，原 Cookie、隔离目录和后台服务未迁移。
