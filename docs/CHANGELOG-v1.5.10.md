# 1.5.10 修改说明

| 文件 | 修改与原因 |
| --- | --- |
| `GeckoWebView.java` | 转交内核真实下载响应；系统文档选择改为后台读取私有文件；按页面身份丢弃过期附件；接收当前文档内容已出现的可信事件；把网络加载尝试与真正文档提交分开，下载不销毁当前页面的通道和状态。 |
| `GeckoUploadFiles.java` | 兼容 SAF/云文档 URI，保留附件名称，限制大小和空间，失败与销毁时清理副本。 |
| `FileDownloads.java` | 从原生响应流保存，不重复请求临时链接；继续使用已有下载管理、保存位置及任务状态；暂停关闭流，校验长度，失败给出合适的重试方式。 |
| `assets/gecko/manifest.json` | 更新内置集成扩展版本为 1.5.10，使已有 Firefox 环境升级时使用新脚本；扩展标识和存储保持原样。 |
| `assets/gecko/content.js` | 安全观察真实页面内容，兼容 document_start 时没有根节点，不修改官方页面内容。 |
| `LoadingUi.java` | 已有可见文档时不再展示阻挡操作的整页错误遮罩，真正关闭的网页仍能显示恢复入口。 |
| `EnvironmentAudit.java` | Firefox 自检在当前内核的扩展隔离世界运行，保持页面、环境和网络授权逻辑；页面/配置变化使结果失效。 |
| `assets/environment-check.js` | 自检取消时清理隐藏测试框架、Worker 和检测请求，不残留到聊天页面。 |
| `AuditReport.java` | 识别 Firefox 版本，区分原系统内核脚本保护与 Firefox 内核保护，不把未覆盖项标为通过。 |
| `WindowHomeActivity.java`、`EnvironmentEditorUi.java` | 记录编辑来源并在退出后返回原环境列表，前往网络页时保留有意的导航。 |
| `AppVersion.java`、`BrandLaunchActivity.java`、`DesignSettingsUi.java`、`AppHub.java` | 启动与关于页面统一读取安装包版本，消除硬编码旧版本。 |
| `ConnectionTrace.java`、`NetworkStatusUi.java` | 复制诊断包含实际应用版本和当前内核，不误报系统 WebView。 |
| `app/build.gradle` | 版本升级为 1.5.10 / code 36，沿用原包名、原签名。 |
| `tests/gecko/GeckoIntegrationTestActivity.java`、`GeckoUploadFixtureProvider.java`、`AndroidManifest.xml`、`run_device.py` | 新增手机版、自检、内容 URI 文本附件和 CSV/Blob 原生下载回归；仅进入受控测试包。 |

完整构建、Android 回归、签名与下载凭据见 [版本验证](../verification/browser-experience-v1.5.10/README.md)。没有改环境隔离、网络核心或后台回复服务，也没有替换 ChatGPT 真实网页。
