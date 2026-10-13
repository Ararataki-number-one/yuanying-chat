# 2.0：官方 GeckoView 与安全资源保护

版本为 2.0.0 / code 53。本版沿用 1.6 的环境配置、入口/出口和 1.7 的模板请求、回读与自检。ChatGPT 仍是官方原网页，登录、草稿、环境目录和固定出口隔离不变。

## 已接入的生产行为

`ResourcePressureController` 在准备创建新的 GeckoRuntime 时读取当前进程能够取得的 Android `ActivityManager.MemoryInfo`。只有明确、有效、五秒内的 `lowMemory` 样本才延期冷启动；它不从某个机型名称或固定阈值推断手机可以运行几个环境。

内存紧张时页面内显示“手机内存暂时紧张，当前环境尚未打开”，提供“重试打开”。保留当前候选地址。这个等待状态不会触发网页加载超时、网络重连或任务重发；用户重试时重新采样，成功创建后重新开始导航期限。创建失败时保留真实错误。

已有运行时和已保存的用户任务恢复优先。冷环境的前台显示、普通网络重连计时器、默认模板队列并不代表已有网页任务，不能绕过低内存等待。内存状态未知时允许用户明确打开，但不进行自动预热，也不授权回收。

已有会话继续使用官方 SDK `setActive(false/true)` 降低空闲页面活跃度。前台、已记录的回复、当前网页正在生成的回复、选择文件与附件准备、未完成附件、下载、导航、恢复、待应用设置、自检、弹窗以及有界的异步检查均保持活动。检查完成或二十秒失效后释放检查活动保护，保留正常轮询间隔。

网页资源观察复用现有 MutationObserver，仅针对明确停止/上传控件和缓存的输入区域，合并相关变化。普通回复文本和无关列表变化不增加全页按钮扫描。事件绑定当前扩展端口、导航代次、文档 ID、递增序列和当前地址；同文档路由经已绑定文档的就绪事件重新绑定。重复选择文件保留所有尚未完成的名称，旧批次回调不能释放新批次。两个完整终态样本后才释放附件保护。

网络传输服务只在新预连接准备处检查压力。已打开环境和正在进行的连接不会因本策略关闭。不存在新的自动销毁会话、杀进程、清数据、驱逐环境或重发任务路径。

## 原生能力范围

继续固定官方 `org.mozilla.geckoview:geckoview:157.0.20261005135250`，AAR SHA-256 为 `15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268`。

`NativeCapabilityManifest` 与 `third-party/sdk/identity-capabilities.json` 明确标记独立时区、Canvas、WebGL、音频和字体的自定义原生控制为不支持。既有官方隐私 API 不被改名为新能力。后续自编译原型必须另有源码、补丁、实际 AAR 与真机上下文和升级回归证据；本版未启用这类后端。

`EnvironmentResourcePolicy.admit` 的测量预算模型仍未接到生产容量限制。未知可用内存不能提出暂停建议；未测量的容量不写成“八环境通过”。启动检查点读取完成不是最新网页状态落盘回执，SDK `flushSessionState` 也不提供可用于安全驱逐的同步确认，因此本版不依据它们销毁网页。

## 验证与证据

- JVM 直接执行生产压力采样/决策代码；Android API 为明确 doubles。完整来源、源码哈希与唯一断言保存为 `resource-pressure-host-results.json`。
- JSDOM 执行真实 observer 模块，验证相关变化节流、序列与旧手势兼容，并验证大量无关文本/list 变化不增加资源扫描。它是受控 DOM 检查，不能作为实际帧率提升证据。
- `ResourcePressureIntegrationActivity` 在独立测试进程使用真实官方 SDK 和生产桥接，验证冷低内存零次 runtime 创建、任务恢复优先、同一候选实际加载、旧期限围栏、保留会话、受控网页状态和重复附件记账。低内存输入及恢复任务明确为合成控制；Android MemoryInfo 和当前应用 PID PSS 为实际观察，排除 Gecko 子进程。
- Android 原始报告、已安装 APK 字节/构建标记、调用 nonce、完整断言与当前源码绑定；资源诊断必须与原 1.6 模型/意图和 1.7 模板 181 项独立检查同时通过。

资源诊断不是物理 ARM 手机容量、真实 ChatGPT 上传、文件选择手势、原生键盘、下载吞吐、登录保持或长时间后台恢复验收。本版不声称网络延迟降低或物理手机最多可运行几环境。候选包通过云端检查后，正式发布仍要求用户真机清单。

## 可复用命令

```sh
python3 tools/gecko/run_profile_host_checks.py --json-jar /path/to/json.jar
python3 tools/gecko/run_resource_observer_host.py --jsdom-module /path/to/node_modules/jsdom
bash tools/gecko/run_identity_host_checks.sh
python3 -m unittest discover -s tests -p 'profile_*_test.py'
python3 tests/gecko/run_profile_features.py --adb /path/to/adb --serial DEVICE --apk app/build/outputs/apk/integration/app-x86_64-integration.apk
python3 tools/gecko/check_resource_evidence.py work/gecko-integration --source FULL_SOURCE_COMMIT
```

Android 运行要求干净已提交源码与完全匹配的实际已安装 `.test` APK。集成构建标记和测试 Activity 不进入正式 release，签名工具与公网发布工具保留拒绝污染检查。
