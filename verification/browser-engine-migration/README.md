# 内嵌浏览器内核评估证据

日期 2026-10-03。用户确认保留独立环境的登录隔离和每个环境的网络设置，插件与网络功能开发继续暂停。

**结果是源码评估，不是新内核实现或登录成功验证。** 完整方案见 [迁移评估](../../docs/BROWSER-ENGINE-MIGRATION.md)。

- `pinned-sources.json`：Mozilla 官方仓库提交 `bf9757d91e2e53b8ab836f2a08bf4c0275fdcd23` 的六个成功快照；状态、大小和 SHA-256。快照保存在被忽略的工作目录中，哈希已与文件核对。
- `assessment.json`：已经确认的接口、未证明的能力、用户约束、当前资源和未执行项。
- `artifact-access.json`：Mozilla Maven 元数据访问被网络代理拒绝，返回 tunnel 403；没有下载、编译或使用未验证的 AAR。
- `sources.json`：初次公开地址请求，保留 Google OAuth 政策代理 403 及两个无效 README 地址的 404；没有把失败请求当作成功的最新政策证据。后续源码已锁定提交。
- `roxy-access.json`：用户确认使用 Windows／macOS Roxy；尝试访问候选产品地址被代理拒绝，未核验 Android SDK、内核下载或源码许可。运行包体与源码构建工作空间分别讨论，优先评估成熟 Android 预编译 SDK。

## 实际证据

| 官方文件 | 源码中的证据 | 能证明的范围 |
| --- | --- | --- |
| `GeckoSessionSettings.java` | `Builder.contextId` 文档描述分隔 Cookie / localStorage；desktop agent 和 viewport 常量 | 存储和桌面设置接口存在，未验证运行结果或每 context 代理 |
| `GeckoRuntime.java` | `Only one GeckoRuntime instance is allowed`；读取自定义配置使用 DebugConfig | 不能简单在一个 runtime 进程创建八个 runtime；生产代理方案需要进一步验证 |
| `GeckoRuntimeSettings.java` | 参数／配置文件 API，配置描述为 debug configuration | 配置入口存在，不能据此保证安全路由和隔离 |
| `WebExtensionController.java` | `ensureBuiltIn`、native messaging；安装 `.xpi` 的签名要求 | 网页驱动有迁移入口，不能保证 Chrome CRX 兼容，也未恢复插件开发 |
| `GeckoSession.java` | 内容、导航、滚动、权限和 Session API | 可嵌入浏览器会话源码可读，现有 WebView 回调仍需逐项适配 |
| `build.gradle` | AAR / Maven publication 配置 | 上游产物发布结构可读；本环境未取得和验证正式产物 |

Chromium 官方构建文档和扩展标记证据沿用 [此前锁定的官方提交](../chrome-extension-feasibility/assessment.json)。至少 100 GB 空闲空间的要求超过当前工作区资源，没有启动内核构建。

没有真机账号验证、代理路由验证或内核运行结果。当前 1.5.6 APK 继续使用原 WebView；修改 UA 与阅读缩放不被记录为登录修复。
