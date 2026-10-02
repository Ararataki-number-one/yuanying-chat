# 1.5.3 会话与网络界面

本轮按 `docs/ui/yuanying_ui_reference.html` 调整会话页外层和网络页。版本为 1.5.3，versionCode 29。环境、下载、设置模块继续使用原有功能。

## 会话页

- 顶部只保留汉堡菜单、可点击的当前环境名称、简洁 / 原网页和更多。移除环境图标、额外默认标签、网站名称和重复操作。
- 第二行一直显示当前窗口的地区、出口 IP、完整代理链延迟和连接状态。点击后进入窗口网络，并滚动到当前窗口。
- 这行读取现有连接状态、固定出口核验结果与统一延迟测量记录。地区使用已有出口地区标注；没有数据时显示未标注、未核验或未测，过期测量显示待更新。
- 原网页仍是原来的 `session.web`。没有加载参考 HTML，没有修改官方 ChatGPT 标题、输入框、模型选择器或消息 UI。简洁 / 原网页沿用原来的切换方法。
- 底部顺序保持会话、环境、下载、网络、设置；状态栏、导航栏、显示缺口与软键盘采用合并安全区。

## 网络页

- 一级 Tab 只有窗口网络、订阅、出口。窗口网络列出全部已创建环境，无需先切换环境。
- 卡片只展示名称与状态、地区 / IP / 延迟、订阅 / 入口方式 / 当前入口，以及编辑网络、测速和更多。
- 编辑、选择订阅、选择入口、选择固定出口、测速、详情与筛选使用居中 Modal。弹窗限制宽度与高度，长内容滚动，保存按钮保留在底部。
- 编辑使用独立候选配置。选择或重新随机不会写入当前窗口；取消整个编辑不会切换连接。点击保存并应用后才校验、保存并调用现有重连方法。保存期间可收起，操作继续执行。
- 自动随机只使用勾选池；手动指定只使用所选节点；更换订阅会清除旧入口和旧池；固定出口独立选择，不参与随机。
- 订阅与出口库汇总已有环境的配置，并使用原有加密存储保存库数据。订阅详情更新可选入口，不直接改变任何窗口的当前连接。没有全局默认出口。
- 旧配置不会在打开页面时自动转换或保存。未保存编辑的旧配置继续使用原有入口选择方式。

## 复用与必要适配

实际 SOCKS5 代理链、固定出口核验、完整线路测速、自动恢复与 WebView 连接仍由原有 `NativeNetwork` / `ChatSession` 执行。为使勾选池与手动指定真正生效，给原入口选择过程增加了范围约束；没有重写网络内核。

跨窗口按钮通过未导出的私有 Provider 进入该窗口已有进程。它不会为读取卡片创建账号 WebView，不改变环境的登录目录、Cookie 或隔离方式。保存前检查原配置摘要，拒绝过期候选；写入失败尝试恢复原配置和缓存。

独立解析订阅调用同一 Mihomo 解析逻辑，使用临时目录和不开放代理监听的短期实例。结果仅用于入口库，结束后停止该实例并删除临时目录。没有用自己实现的解析器替代原解析功能。

## 修改文件与用途

下列路径相对于仓库根目录。

| 文件 | 修改原因 |
| --- | --- |
| `app/src/main/java/local/pocketchat/DesignChrome.java` | 重排会话顶部和真实网络状态行，接入原环境切换与模式切换。 |
| `app/src/main/java/local/pocketchat/MainActivity.java` | 应用安全区；更多菜单改为居中；销毁页面时清理网络 UI 读取任务。原 WebView 创建、登录和生命周期代码沿用。 |
| `app/src/main/java/local/pocketchat/AppHub.java` | 保留五个导航目标；接入新网络页和定位当前窗口；版本文字更新。 |
| `app/src/main/java/local/pocketchat/Ui.java` | 增加独立汉堡菜单图形，已有图标保留。 |
| `app/src/main/java/local/pocketchat/ReferenceUi.java` | 会话 / 网络页专用颜色、间距、卡片、按钮、居中弹窗、安全区与底部导航样式。 |
| `app/src/main/java/local/pocketchat/DesignNetworkUi.java` | 删除旧五栏网络表现层，保留现有调用入口并转到新页面。 |
| `app/src/main/java/local/pocketchat/NetworkWorkspaceUi.java` | 三栏列表、窗口卡片、候选编辑、详情、筛选、真实测速与保存反馈。 |
| `app/src/main/java/local/pocketchat/EntryPickerUi.java` | 入口池复选 / 手动单选、候选随机、确认与取消；大订阅使用可复用列表项。 |
| `app/src/main/java/local/pocketchat/NetworkDraft.java` | 与当前连接分开的候选配置，订阅切换清理和保存校验。 |
| `app/src/main/java/local/pocketchat/EntrySelection.java` | 将用户所选入口范围交给原选择流程；校验节点归属及随机池。 |
| `app/src/main/java/local/pocketchat/NetworkCatalog.java` | 汇总已有订阅 / 出口、加密库缓存与并发合并，不设置全局默认。 |
| `app/src/main/java/local/pocketchat/WindowNetworkState.java` | 会话和网络页共用真实状态，明确处理缺失和过期数据。 |
| `app/src/main/java/local/pocketchat/NetworkBridge.java` | 在后台向目标窗口发送私有操作，返回保存 / 测速结果。 |
| `app/src/main/java/local/pocketchat/NetworkUiProvider.java` | 在已有窗口进程中调用原网络方法；校验候选、避免并发冲突并处理写入失败。 |
| `app/src/main/java/local/pocketchat/NativeNetwork.java` | 原解析和启动步骤供短期订阅预览复用；增加入口范围约束及 UI 缓存 / 状态快照。代理链与核验方法沿用。 |
| `app/src/main/java/local/pocketchat/NetworkMetricsUi.java` | 将已有指标同步到新会话顶部，保留原测速口径。 |
| `app/src/main/AndroidManifest.xml` | 版本 1.5.3 / 29；注册八个未导出 Provider，使用已有窗口进程。 |
| `build.ps1` | 更新 APK 文件名，测试包使用独立 Provider authority，注册隔离测试活动。 |
| `tests/CompactModeTestActivity.java` | 核对新顶部、网络定位和原模式切换 / 草稿保留。 |
| `tests/DesignUiTestActivity.java` | 更新顶部和三个网络 Tab 的旧界面断言。 |
| `tests/NetworkReferenceTestActivity.java` | 用真实 Mihomo 解析 / 选择器和真实加密保存 / 跨进程分发验证候选、随机池、取消、保存及页面。 |
| `tests/NetworkBridgeProbeActivity.java` | 仅测试包使用的第七窗口连接回调夹具，避免依赖私人代理或账号。 |
| `docs/ui/yuanying_ui_reference.html` | 保存用户提供的视觉参考，未加入运行时 assets。 |
| `docs/CHANGELOG-v1.5.3.md` | 本轮行为、边界和逐文件修改说明。 |
| `README.md` | 当前版本、下载入口和三栏网络功能说明。 |
| `docs/BUILD.md` | 更新发布 APK 路径。 |
| `verification/chat-network-reference/` | 本轮构建、测试、截图和未完成验证的记录。 |

## 验证

构建、模拟器检查、截图和适用范围见 [本轮验证记录](../verification/chat-network-reference/README.md)。测试使用独立包名；网络回调夹具与真实公开代理连通性分别说明。未连接用户真机或登录真实账号。
