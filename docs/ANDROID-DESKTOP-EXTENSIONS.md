# Android 电脑版网页 · Chrome 扩展方案

目标是在 Android App 内的电脑版网页安装和使用真实 Chrome 扩展。扩展按环境管理；第一轮兼容性样本选择 Tampermonkey（油猴）、Dark Reader 和 uBlock Origin Lite。用户已明确选择 Chrome 扩展，并授权由项目选择常见样本。

**当前状态：完成源码可行性评估和交互方案，功能尚未实现，没有新的扩展 APK。** 现有 1.5.4 的电脑版使用 Android System WebView；切换桌面访问标识和视口不会增加 Chrome 扩展安装、后台服务或扩展 API。

## 界面设计

沿用“新建环境 → 基本信息 → 网页显示方式”和“编辑环境 → 浏览器”。选择电脑版后显示一行“Chrome 扩展”，点击进入当前环境的扩展管理。会话顶部继续保留现有布局。

扩展管理采用屏幕中央弹窗：列表只显示扩展名称、启用状态和更多菜单；主要操作为“安装扩展”。权限说明、版本、更新和卸载放在详情中。没有扩展时显示“还没有扩展，安装后可在这个环境使用”，不增加统计面板。安装来源优先官方商店，本地包导入需由实际内核支持并完成签名、来源与权限处理。

配置选择先作为环境候选，点击“保存并应用”才切换引擎或改变启用范围。内核安装扩展需要独立的实际权限确认，不能仅保存一个表单开关便显示“安装成功”。卸载、启停及权限变化必须使用内核 API 的真实结果；失败原因在当前弹窗展示。取消配置不改变当前窗口。

手机版不执行这一模式的扩展。切回手机版保留已安装扩展及设置，重新打开电脑版可继续使用。扩展状态和存储按环境隔离；第一轮不提供“全局启用”。

## 内核选择

| 方案 | 已核实的证据 | 结论 |
| --- | --- | --- |
| 当前 Android WebView | 项目使用 `android.webkit.WebView` 和 AndroidX WebKit；已有桌面模式只设置 UA、viewport 和缩放 | 不能用现有 API 实现真正 Chrome 扩展，不发布仅有开关的空功能 |
| 上游 Chromium 的 Android 桌面构建 | 官方源码已有 `is_desktop_android`、`enable_desktop_android_extensions`、`enable_extensions_core`；注释明确说明扩展代码逐步移植，仍有未移植部分 | 作为首选技术验证路线；先构建独立实验浏览器，再验证三个扩展和项目功能，不能据此宣称全面兼容 |
| GeckoView | 官方 `WebExtensionController.install` 接受 `.xpi`，通常需要 Mozilla 签名；有可嵌入的扩展接口 | 可用于 Firefox / WebExtension 路线，不能据此承诺直接安装 Chrome `.crx`；用户当前目标不选该路线 |
| Kiwi | 上游 README 明确声明 2025 年 1 月后不再维护 | 不作为后续维护基础 |

还检查了 `mises-id/mises-browser` 默认分支：本次拿到的 `714d86a…` 源码标为 Chromium 77，README 仍为旧 Kiwi。这个仓库不构成当前 Mises 产品内核或新版扩展兼容性的证据，不采用其旧源码。

## 首轮扩展验收

这些是常见测试样本，没有核验实时安装量或热门排名；也没有完成在本 App 中安装或运行。

| 扩展 | 官方入口 | 必须验证的实际行为 |
| --- | --- | --- |
| Tampermonkey | [Chrome 商店](https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo) | 安装正式包、打开管理页、创建仅匹配测试页面的简单脚本、执行和禁用、重启后保留；不同环境的脚本和扩展存储独立 |
| Dark Reader | [Chrome 商店](https://chromewebstore.google.com/detail/dark-reader/eimadpbcbfnmbkopoojfekhnkhdbieeh) | 官方 MV3 包的后台 worker、scripting、storage 和弹出页可用；ChatGPT 明暗切换、单站设置和重启后保留；不能遮挡输入、模型或消息 |
| uBlock Origin Lite | [官方项目](https://github.com/uBlockOrigin/uBOL-home) | 安装正式 MV3 包、打开面板、声明式网络规则、开启和关闭规则、重启后保留；使用本地测试广告请求验证实际拦截 |

Dark Reader 上游 `manifest-chrome-mv3.json` 已确认使用 Manifest V3、后台 service worker、scripting 和 storage。uBlock Origin Lite 上游说明其为 MV3 声明式拦截器。Tampermonkey 的公开 GitHub 仓库只含至 2.9 的旧源码，更新版本采用专有许可；测试必须使用正式发行包，不能把旧仓库当作最新版兼容证据或直接内置重新分发。

## 项目迁移边界

现有源码中有 12 个文件直接依赖 WebView / AndroidX WebKit。它们涉及真实网页、登录 Cookie、附件、下载、网络请求与 service worker 防护、页面观察、隐私脚本和草稿恢复。更换内核不能只替换 UI 中一个 View。

采用逐步接入，先保留当前 WebView 环境和已有目录，再为扩展模式建立独立的内核 profile：

1. 定义浏览器引擎接口，覆盖页面视图、导航、可信站点消息、JavaScript 执行、Cookie、附件与下载回调；WebView 先作为默认实现。
2. 在独立实验包验证 Chromium 桌面构建及三个真实扩展。验证 ARM64 手机，x86_64 只作为辅助；桌面构建能编译不等于适合手机宽度和触控。
3. 将每个环境映射到独立 Chromium profile。扩展安装、权限、storage、后台 worker 和 cookies 必须随 profile 隔离；不能只隔离表单配置。
4. 复用现有网络配置、订阅解析、SOCKS5、固定出口和核验。新内核的页面、扩展后台及 worker 请求必须经过该环境连接，验证断线保护、VPN 状态和代理切换；WebView 的 `ProxyController` 与 `ServiceWorkerController` 不能直接用于另一个内核。
5. 接入真实 ChatGPT 网页和现有观察、回复、下载、草稿及后台功能。覆盖网页重载、SPA 导航、插件报错和后台恢复，正常环境及网络功能验证通过后再开放入口。

旧 WebView 的登录目录和 Cookie 保留，不自动搬运、清空或覆盖。新内核可能需要重新登录，必须在选择扩展模式时说明。回退到原环境后仍使用原 WebView 数据。不得声称换内核可以无感保留全部登录。

## 当前阻塞与下一步

[Chromium 官方 Android 构建说明](https://github.com/chromium/chromium/blob/cc2df82017e1a381bbf9e19b438c1ef7bb82695e/docs/android_build_instructions.md)要求至少 **100 GB 空闲磁盘**。当前工作空间只有约 **26.4 GiB** 空闲；内存足够，但没有已验证可嵌入的扩展内核产物。未启动大规模源码下载或核心构建，不能交付 Chrome 扩展安装包。

继续实现需要具有至少 100 GB 空闲磁盘的 Chromium 构建环境，或来源、版本、完整性和扩展接口均可验证的兼容内核 SDK。准备后先完成独立内核实验和上述三个扩展检查，再迁移现有项目。现有 APK 和版本号保持 1.5.4；本轮只有方案及证据，不以脚本插件代替用户要求的 Chrome 扩展。

源码检查、环境资源及未执行项目见 [评估证据](../verification/chrome-extension-feasibility/README.md)。
