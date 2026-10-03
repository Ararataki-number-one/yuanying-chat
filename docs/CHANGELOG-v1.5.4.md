# 1.5.4 · 按环境选择手机版 / 电脑版

创建环境的第一步增加“网页显示方式”，选择“手机版”或“电脑版”，确认创建后才保存。已有环境在“编辑环境 → 浏览器”修改，取消和存草稿不会应用显示方式。旧环境升级后保持手机版；每个环境独立保存，环境列表中的电脑版提示复用已有辅助信息行。

电脑版继续使用同一个真实 ChatGPT WebView，使用已安装 Chromium 的实际版本生成桌面访问标识、1024 像素布局视口及原生双指缩放。加载前脚本仅调整 ChatGPT 顶层页面的 viewport 元数据，正文、标题、输入框、模型选择器和消息结构不变。“简洁 / 原网页”的现有逻辑保持。

保存正在使用的环境前，复用现有只读网页检查、阅读位置保存和草稿归档。遇到回复、连接或其他未完成操作时先提示等待；草稿保留失败、页面已改变或草稿超过快照容量时不应用修改。只有显示方式改变时复用当前网页加载流程，网络连接实现和后台服务没有新增逻辑。

## 修改文件

| 文件 | 修改原因与行为 |
| --- | --- |
| `app/src/main/java/local/pocketchat/BrowserDisplay.java` | 集中显示名称、真实版本 UA、忙碌状态判断和限于顶层页面的视口策略，避免不同入口各自实现 |
| `app/src/main/java/local/pocketchat/BrowserDisplayUi.java` | 创建和编辑复用同一紧凑选择控件 |
| `app/src/main/java/local/pocketchat/ProfileCatalog.java` | 数据库 v4 → v5，仅追加默认值为手机版的列；共享环境目录是显示方式的唯一配置来源 |
| `app/src/main/java/local/pocketchat/WindowHomeActivity.java` | 创建表单、确认页、返回恢复和保存接入显示方式；列表辅助行提示电脑版 |
| `app/src/main/java/local/pocketchat/EnvironmentEditorUi.java` | 浏览器页接入选择、配置草稿与保存；保存前保护当前网页草稿，失败时恢复编辑并显示原因 |
| `app/src/main/java/local/pocketchat/BrowserPrivacy.java` | 复用浏览器设置入口应用访问标识、宽视口、缩放和加载前脚本；缺少 WebView 能力时提示更新 |
| `app/src/main/java/local/pocketchat/ChatSession.java` | 显示方式变化时走已有网页加载流程，加载前应用设置；不重建 WebView、不清除 Cookie 或登录目录 |
| `tests/BrowserDisplayPolicyTest.java` | 23 项主机策略检查，包括恢复手机版、实际浏览器版本和五类忙碌状态 |
| `tests/browser-display-viewport.cjs` | 12 项 DOM 检查，覆盖正文及草稿不变、SPA 更新、重复标签、iframe、早期加载与缩放限制 |
| `tests/browser-display-migration.py` | 8 项 SQLite 检查，使用实际新旧建表和升级语句验证字段保留、默认值和环境独立保存 |
| `tests/WindowHomeTestActivity.java` | 更新数据库迁移终点，补充创建前配置不落地与返回恢复选择的原生用例；本轮只编译，未执行 |
| `app/src/main/AndroidManifest.xml`、`app/src/main/java/local/pocketchat/AppHub.java`、`build.ps1` | 版本更新为 1.5.4 / 30，更新关于页和构建文件名 |
| `README.md`、`docs/BUILD.md`、本文件、`verification/environment-browser-display/` | 使用入口、下载信息、复现方法、构建和验证证据 |

## 验证与限制

发布 APK 和独立测试 APK 编译、签名、对齐及包版本检查通过；23 + 12 + 8 = 43 项主机检查通过。原版证书用于发布 APK，私钥不加入源码和公开附件。

本轮没有连接真机，也没有登录真实账号。DOM 检查不代表完成 Android WebView 的页面布局、双指缩放、键盘、覆盖安装后登录保持或多进程运行验证。电脑版仍运行 Android WebView，不能等同完整桌面 Chrome；实际功能由网页及账号提供。上一轮云模拟器的 WebView 渲染崩溃和网络恢复耗时未通过项保留在旧验证记录中，本轮不声称解决。

详细结果和手机核验清单见 [验证记录](../verification/environment-browser-display/README.md)。
