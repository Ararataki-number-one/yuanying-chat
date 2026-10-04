# 1.5.14 独立网络服务与性能策略

底层把代理数据通道从浏览器所在的环境进程分离。专用 Android 前台服务持有各环境的真实 Mihomo 内核；界面和策略通过应用私有 Messenger 命令控制，内核退出通过监督事件通知。恢复先验证配置和固定出口，再接管已有内核与端口。

## 修改文件

未注明路径的 Java 文件均位于 `app/src/main/java/local/pocketchat/`。

| 文件 | 修改与目的 |
| --- | --- |
| `NetworkTransportService.java` | 新增独立 `:network` 服务，每环境命令串行、不同环境并行；监督内核退出，以实例代号阻止旧回调覆盖新实例；只清理身份核实的旧进程，明确确认停止后才允许删除。 |
| `NetworkTransportClient.java` | 新增应用内 IPC 客户端，关联请求和回复、接收状态事件；服务死亡时立即使网络准入失效，恢复前保持阻断。 |
| `NativeNetwork.java` | 将正式环境内核交由服务持有；配置指纹和原子运行记录支持原内核接管；保存入口索引与实际 DNS，重新核验固定出口；沿用原订阅解析、SOCKS 链和发送前核验。 |
| `NetworkOptimizationPolicy.java` | 限制空闲维护频率与每轮节点数，持续轮换允许池中的节点；统一入口模式和网站响应状态。 |
| `WebsiteProbe.java` | 通过专门候选监听器测网站首次响应和复测，不带账号信息、不跟随跳转；仅关闭检测连接，不改浏览器路由。 |
| `NetworkDns.java` | 通过固定出口验证真实 DNS 响应，按环境、订阅和出口保存选择；结果有效期 24 小时，下次正常连接生效。 |
| `RouteQuality.java` | 新增网站专用评分记录与排序；沿用样本数、波动、成功率、冷却和持续胜出的切换阈值。 |
| `EntrySelection.java`、`NetworkDraft.java` | 增加低延迟允许池约束；更换订阅清理候选，所有编辑保持 draft，保存并应用才切换。 |
| `EntryPickerUi.java` | 增加低延迟优先模式及允许池选择；旧随机、手动操作保留，兼容居中弹窗和大字体。 |
| `NetworkWorkspaceUi.java`、`NetworkMetricsUi.java`、`WindowNetworkState.java`、`ExitIpUi.java` | 显示真实入口模式、网站检测和 DNS 信息；辅助数据放在详情与测速结果，保持列表密度。 |
| `ChatSession.java` | 用户开始提交、导航、上传或下载时取消后台网络检测；浏览器和回复服务继续使用原实现。 |
| `NetworkUiProvider.java` | 低延迟模式未预选入口时保留历史成功入口；删除环境要求收到服务的停止确认，避免连接未关闭就清数据。 |
| `app/src/main/AndroidManifest.xml`、`app/build.gradle` | 注册私有独立前台服务及其用途，正式版本更新为 1.5.14 / code 40；测试 TLS 资产仅编入 integration。 |
| `tests/gecko/NetworkOptimizationIntegrationActivity.java`、`NetworkTransportLifecycleActivity.java`、`run_network_performance.py` | 真实 Android 和 Mihomo 的两个 SOCKS 跳、HTTPS、DNS、取消检测，以及控制进程 / 内核 / 网络服务退出与重建回归；合成数据和证书仅用于独立测试包。 |
| `tests/gecko/UiVisualIntegrationActivity.java`、`run_ui_visuals.py`、`AndroidManifest.xml` | 原生拍摄新增模式在 360 dp、412 dp 和大字体下的布局，并保留既有界面验证。 |
| `tests/gecko/assets/README.md`、`network-fixture.p12` | 声明公开、仅测试的本地 TLS 证书，正式包禁止包含该资产。 |
| `.github/workflows/gecko-integration.yml`、`tools/gecko/publish_ci.py` | 正式编译后先执行网络底层回归，再执行原生界面和浏览器回归，保存与源码匹配的证据。 |
| `tools/sign-apk.py`、`tools/publish-gecko-release.py` | 验证正式包没有测试组件和合成 TLS 资产；发布要求独立服务、网络性能、界面与旧回归同时通过。 |
| `docs/NETWORK-ARCHITECTURE.md`、`NETWORK-PERFORMANCE-PLAN.md`、`RELEASE-v1.5.14.md` | 记录架构、性能规则、启用路径与验收边界。 |

## 使用方式与边界

“网络 → 编辑网络 → 入口选择 → 低延迟优先”，勾选允许使用的节点，再保存并应用。固定出口不随机；随机和手动模式不会被自动改成优选模式。健康线路只在空闲且改进证据足够时切换。

独立服务保护代理内核及其缓存的生命周期。浏览器进程退出仍会关闭它自身的 HTTP 连接；原网页请求不可能靠保留内核继续完成。控制面和管理页仍有原有轮询，不能称整个网络都已事件化。真实用户线路的延迟收益、ARM 真机与长期登录需实测。

设计见 [底层架构](NETWORK-ARCHITECTURE.md) 与 [性能方案](NETWORK-PERFORMANCE-PLAN.md)。实际编译、回归、APK 与公网证据见 [版本验证](../verification/network-performance-v1.5.14/README.md)。
