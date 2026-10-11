# 1.5.17 · 聊天交互性能

用户反馈聊天页滚动与输入卡顿。代码中确认了两类热点：检测回复时反复读取、转换和传输长正文；周期性 UI 更新同步查询数据库、解密文件并重复修改未变化的控件。

## 网页观察与回复完成

| 文件 | 修改与作用 |
| --- | --- |
| `app/src/main/assets/web-performance.js` | 正文、附件和提问使用同一组按 DOM 节点与版本失效的缓存；缓存消息节点列表，文本流式变化保留有效的列表结构。 |
| `app/src/main/assets/page-driver.js` | 生成期间仅返回真实生成状态、绑定信息和内容版本；终态完整采集，后续相同版本省略重复正文。保留真实网站及原网页控件。 |
| `app/src/main/java/local/pocketchat/ChatSession.java` | 按任务、地址、回复标识和内容版本严格复用完整采集；内容变化立即重新采集，保留至少三次稳定样本和两秒观察窗口。 |
| `app/src/main/java/local/pocketchat/ReplyState.java` | 轻量观察下仍显示真实生成状态。 |

## 原生刷新与后台存储

| 文件 | 修改与作用 |
| --- | --- |
| `DesignChrome.java` / `NetworkMetricsUi.java` | 合并重复更新，只修改变化的文字、颜色和模式背景；环境名称在后台刷新。 |
| `DesignUi.java` / `AppSettings.java` | 背景绘制复用坐标与渐变，设置在绘制之外读取；设置变更使存活的背景实例及时失效。 |
| `ProfileCatalog.java` | SQLite 启用 WAL；常规环境心跳在单一后台写入队列中按环境合并，使用写入版本和环境 generation 防止旧结果覆盖新状态。 |
| `EnvironmentAudit.java` | 周期性配置解密、核对和自动持久化在后台执行；只接收仍属于当前连接、环境和配置的结果。手动接受基线仍保持可确认的同步结果。 |
| `NetworkRegion.java` / `FileSnapshotCache.java` | 地区和延迟快照按环境文件路径缓存，UI 不执行文件检查或解密；后台识别文件替换、删除，旧读取不能覆盖新写入。 |
| `NetworkWorkspaceUi.java` | 网络列表在后台预读地区与待应用草稿标记，绘制卡片不逐个解密。 |
| `NetworkUiProvider.java` | 每秒检查待应用网络配置时，数据库读取和草稿解密由后台线程执行；应用前重新核对环境身份和操作状态，避免空闲聊天被周期性磁盘访问打断。 |
| `MainActivity.java` / `LoadingUi.java` / `WindowHomeActivity.java` | 内容没变化时不重复更新文字；隐藏进度区域不重复格式化；管理页恢复时刷新背景设置。 |
| `SecretStore.java` / `UiPerfStats.java` | 增加默认关闭的本地回归计数，用于验证 UI 热路径没有同步数据库和加密文件工作。未改变加密格式或密钥。 |

## 验证与交付

新增 `reply-observation.test.cjs` 和 `FileSnapshotCacheTest.java`；扩展实际 Android 的紧凑顶部与网络回归。独立 `GeckoPerformanceIntegrationActivity.java` / `run_gecko_performance.py` 对比固定的 1.5.16 观察脚本与当前脚本，在实际 Gecko 和原生扩展桥上读取长会话；历史脚本仅存在于测试包。

CI 保留原浏览器、网络、通知和视觉回归。`check_performance_evidence.py` 在签名发布流程中要求源码一致的真实 Android 证据、完整终态内容和环境隔离检查。正式 APK 排除新增测试组件及历史脚本，使用原签名并更新公网自动更新源。

没有替换真实 ChatGPT 页面、改变浏览器生命周期、清理登录数据或重建网络核心。受控环境数据不代表特定真机的帧率，未知异常画面不能凭性能检查推断已修复。
