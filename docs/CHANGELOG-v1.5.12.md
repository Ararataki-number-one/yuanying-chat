# 1.5.12 修改说明

本版改善环境管理、编辑时机和网页阅读空间，继续使用现有真实网页、独立浏览器目录、网络核心和回复服务。正式包使用原签名，版本为 1.5.12 / code 38。

## 使用方式

- 节点列表会从名称、城市和国旗识别地区。这是入口名称提示；会话与窗口网络的出口地区按实际出口 IP 查询，查询失败保留未知或用户填写的地区。
- 环境卡片的“更多 → 删除环境”会先确认，再停止该环境并清理登录、本地会话、草稿和配置。已有下载文件、其他环境和共享订阅/出口保留。最后一个环境需要先创建其他环境才能删除；清理中断可从列表继续清理。
- 回复过程中可以编辑并保存网络、网页显示和保护等级。保存后显示待应用，当前操作结束再应用；网络详情可以取消待应用的配置。网页显示调整前会保存草稿，并再次检查是否正在输入或提问。
- 会话顶部从约 93 dp 压缩至 72 dp；仍可点击环境名称切换、点击网络行定位当前窗口。真实网页、底部五项导航与系统安全区保留。
- Firefox 的强化保护启用官方原生抗指纹能力，标准保护保留网站兼容性。强化保护可能影响验证和音视频，可在各环境独立调整。

## 修改文件

| 文件 | 修改与原因 |
| --- | --- |
| `NodeRegion.java`、`EntryPickerUi.java` | 识别名称与国旗中的地区，避免把冲突名称或字母片段误判为国家；入口列表增加紧凑地区提示。 |
| `NetworkRegion.java`、`WindowNetworkState.java` | 通过当前环境的受保护线路查询实际出口 IP 地区；加密缓存，不把入口名称当成出口核验。连接失败和被保护开关阻断的窗口不再进入已连接筛选。 |
| `NetworkChanges.java`、`NetworkDraft.java` | 单独保存加密候选配置和当前基线；保存前验证订阅节点池，排队期间不改变正在使用的线路。 |
| `NetworkUiProvider.java` | 验证与保存移到工作线程；回复期间接受候选配置，空闲后调用原连接逻辑应用；失效候选显示需要重新编辑；删除时停止环境写入者和网络组件。 |
| `NetworkWorkspaceUi.java` | 应用代理窗口进入正确的编辑表单；保留候选入口；展示/取消待应用配置；说明手机 VPN 保护开关的实际作用。 |
| `DeferredBrowserSettings.java`、`EnvironmentEditorUi.java` | 将希望使用的网页设置与正在使用的设置分开，允许回复期间保存；应用前记录草稿与阅读状态，再核对网页是否出现新输入或新任务。 |
| `ChatSession.java`、`WebReplyObserver.java` | 将待应用设置纳入后台运行条件，回复完成后继续处理；读取草稿期间仍识别用户发起的新提问，防止随后刷新覆盖操作。 |
| `EnvironmentDeleteActivity.java`、`DownloadLibrary.java`、`NetworkCatalog.java` | 独立维护进程先停浏览器/代理再清理单个环境，保留已下载文件和待删除环境仍持有的共享订阅缓存；默认环境采用明确的清理范围，保留全局库、更新和其他环境；先删除失效浏览器锁链接，不跟随链接删除其他文件。 |
| `ProfileCatalog.java`、`WindowHomeActivity.java` | 增加删除确认、清理状态与重试；使用环境代次拒绝旧进程的延迟写入，避免已删环境再次出现。 |
| `ProfileContext.java`、`Profiles.java`、`ProfileUi.java`、`MainActivity.java` | 创建时清除已删槽位的旧偏好缓存，管理进程重新读取其他环境偏好；删除中的环境不能再次打开，失效页面退出时不再启动网络组件。 |
| `DesignChrome.java` | 缩小顶部高度、字号和空白，保留主要操作及状态行。 |
| `GeckoWebView.java`、`BrowserPrivacy.java`、`assets/gecko/background.js`、`assets/gecko/manifest.json` | 等待 Firefox 原生保护设置确认后加载网页；强化档启用官方抗指纹，界面说明与实际启用状态一致。 |
| `assets/page-driver.js` | 识别内层消息编号和当前回复的完成操作；旧回复或代码块的复制按钮不能结束当前等待，兼容已有原生等待任务。 |
| `AppUpdateManager.java` | 更新通知使用独立编号，避免覆盖默认环境的回复通知。 |
| `AndroidManifest.xml`、`app/build.gradle` | 注册私有删除维护页面，升级版本号；不迁移登录目录。 |
| `tests/browser-runtime/NodeRegionTest.java` | 验证国家、城市、国旗、冲突名称与未知地区等实际解析行为。 |
| `tests/gecko/EnvironmentManagementIntegrationActivity.java`、`GeckoIntegrationTestActivity.java`、`AndroidManifest.xml`、`run_device.py` | 实际 Android 验证回复期间保存、后台应用、内层消息识别、原生保护、删除与槽位复用；这些测试组件不会进入正式 APK。 |
| `.github/workflows/gecko-integration.yml`、`tools/gecko/publish_ci.py`、`tools/sign-apk.py` | 执行并保存新增检查，正式签名时确认测试组件不存在。 |

## 截图问题对应

附件读取、原生下载、加载提示遮挡、自检入口、编辑取消返回和实际版本显示沿用 1.5.10/1.5.11 的修复，并继续回归。此版新增回复结束识别、正确网络编辑入口与筛选，以及 Firefox 原生强化保护。

“仅在连接手机 VPN 时联网”只控制手机网络模式；应用代理模式使用原有代理失败阻断逻辑。测试覆盖没有 VPN 时阻断，尚未完成真机 VPN 连接后断开的验收。网页上传与生成文件下载使用本地受控数据回归，不能据此保证所有真实账号和已失效服务端链接都可用。手机版偶发白屏、真实账号的长期登录和厂商后台策略仍需真机与真实网页复核。

[构建、Android 与公网验证](../verification/environment-management-v1.5.12/README.md)。
