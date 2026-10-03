# 1.5.9 网页缩放、登录保存和进程恢复

电脑版的“网页缩放”可从 100% 降到 60%。小于 100% 时扩大原生浏览器的排版区域并按比例显示同一网页，允许展示更多内容；大于 100% 继续使用浏览器原生缩放。每个环境独立保存选择。缩放不重新加载网页，不替换 ChatGPT 的页面或输入框。

浏览器采用 SDK 支持变换的 TextureView，启动时选定并保持同一显示方式，避免缩小与放大之间更换显示 Surface 导致黑屏。布局和触摸后同步实际屏幕位置，程序缩放也保留正确的屏幕原点，避免点击位置、登录弹窗或输入位置偏移。新操作取消尚未完成的程序缩放。

放大手势先达到 Android 的识别阈值，再施加目标比例；阅读控制器测量真实页面缩放并有限次校准，避免选择 130% 但实际仅放大到约 113%。

原先只有主进程的 AndroidX Startup Provider。其他环境运行在独立 Android 进程，浏览器依赖的 ProcessLifecycleOwner 在这些进程没有初始化，无法收到正确的前后台状态。现在每个环境使用独立、不导出的 Startup Provider，按 AndroidX 官方机制初始化。环境数据与子进程隔离保持原样。

浏览器通过官方 Cookie API 将会话 Cookie 保存到当前环境私有扩展存储，等待恢复完成再打开网页。保留 Secure、HttpOnly、SameSite、host-only、域及分区属性，不添加服务器过期时间。原生已有 Cookie 优先。网站删除 Cookie、退出登录和清理环境会更新保存记录；恢复发生 API 错误时保留完整记录，不用部分结果覆盖它。

SDK 批量清理不保证逐条发出 Cookie 删除事件。宿主读取 Cookie 时会先从真实存储更新保存记录，再返回结果，防止已清理 Cookie 在重启后恢复。

SDK 页面状态通过回调保存到环境私有、不可备份的 AtomicFile。网页进程被关闭时，在前台且网络保护允许的情况下自动重新打开同一环境，使用 SDK 恢复历史、滚动、缩放及可保存的表单，并复用已有页面恢复逻辑。每分钟最多自动恢复两次，连续失败保留手动重试。不会自动重发消息，也不会把登录中转页保存为下次打开的对话。

## 修改文件与原因

| 文件 | 修改及目的 |
| --- | --- |
| `BrowserReadingPolicy.java` | 最小缩放从 100% 改为 60%，无效值仍回到 100%，旧版本设置继续按原规则迁移。 |
| `BrowserReading.java` | 使用真实视口与实际显示比例协调缩小、原生放大、手势和环境缩放记忆；登录页使用自己的正常显示。 |
| `BrowserReadingUi.java` | 说明实际范围与阅读方式，不在会话顶部增加元素。 |
| `GeckoWebView.java` | 稳定的原生显示 Surface、坐标与程序手势取消；等待 Cookie 恢复；保存 SDK 状态；受控自动恢复及同一环境手动恢复。 |
| `BrowserSessionStore.java` | 单线程、限量、原子写入的私有 SDK 状态文件；IO 不占界面线程。 |
| `EnvironmentLifecycleProvider.java` | 在七个独立环境进程按 AndroidX Startup 初始化生命周期。 |
| `ChatSession.java` | 后台前保存页面状态，返回时恢复已关闭页面；手动重试优先恢复 SDK 状态；跳过登录中转 URL。 |
| `assets/gecko/background.js` | 使用官方 API 保存和恢复会话 Cookie，保留属性、删除和失败处理；等待完成后通知原生宿主。 |
| `assets/gecko/manifest.json` | 加入私有存储权限并更新内置扩展版本。 |
| `app/build.gradle`、`AndroidManifest.xml` | 1.5.9 / code 35；明确 Startup 依赖，声明独立进程 Provider。 |
| `tests/gecko/GeckoIntegrationTestActivity.java`、`run_device.py` | 实际 Android 浏览器渲染、可信点击与键盘输入；不重新加载的环境切换、Cookie 重启和退出登录、清理、SDK 关闭与恢复。 |
| `tests/browser-reading-host/` | 生产阅读控制器缩小、手势、尺寸及迁移回归。 |
| `tests/browser-runtime/session-cookies.test.cjs` | 生产扩展的属性、分区、删除、现有 Cookie 优先和部分恢复失败回归。 |
| `.github/workflows/gecko-integration.yml`、`tools/gecko/publish_ci.py` | 构建后执行新增检查并保存仅含模拟数据的证据。 |

## 验证范围

最终构建、Android 回归和原签名检查见 [本版验证记录](../verification/browser-experience-v1.5.9/README.md)。受控页面验证客户端保存与恢复，不等同于通过 Google / ChatGPT 的真实账号验收。没有连接 ARM 真机；网页关闭测试注入 SDK 的关闭契约，没有声称实际发生了系统低内存回收。

网站主动使登录失效时仍需重新登录。不同浏览器内核的登录存储继续分别保存。插件与网络新功能继续暂停。
