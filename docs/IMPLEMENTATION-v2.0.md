# 2.0：GeckoView 单类输入修正与安全资源保护

版本为 2.0.0 / code 53。本版沿用 1.6 的环境配置、入口/出口和 1.7 的模板请求、回读与自检。ChatGPT 仍是官方原网页，登录、草稿、环境目录和固定出口隔离不变。

## 已接入的生产行为

`ResourcePressureController` 在准备创建新的 GeckoRuntime 时读取当前进程能够取得的 Android `ActivityManager.MemoryInfo`。只有明确、有效、五秒内的 `lowMemory` 样本才延期冷启动；它不从某个机型名称或固定阈值推断手机可以运行几个环境。

内存紧张时页面内显示“手机内存暂时紧张，当前环境尚未打开”，提供“重试打开”。保留当前候选地址。这个等待状态不会触发网页加载超时、网络重连或任务重发；用户重试时重新采样，成功创建后重新开始导航期限。创建失败时保留真实错误。

已有运行时和已保存的用户任务恢复优先。冷环境的前台显示、普通网络重连计时器、默认模板队列并不代表已有网页任务，不能绕过低内存等待。内存状态未知时允许用户明确打开，但不进行自动预热，也不授权回收。

已有会话继续使用官方 SDK `setActive(false/true)` 降低空闲页面活跃度。前台、已记录的回复、当前网页正在生成的回复、选择文件与附件准备、未完成附件、下载、导航、恢复、待应用设置、自检、弹窗以及有界的异步检查均保持活动。检查完成或二十秒失效后释放检查活动保护，保留正常轮询间隔。

网页资源观察复用现有 MutationObserver，仅针对明确停止/上传控件和缓存的输入区域，合并相关变化。普通回复文本和无关列表变化不增加全页按钮扫描。事件绑定当前扩展端口、导航代次、文档 ID、递增序列和当前地址；同文档路由经已绑定文档的就绪事件重新绑定。重复选择文件保留所有尚未完成的名称，旧批次回调不能释放新批次。两个完整终态样本后才释放附件保护。

登录或授权弹窗关闭后，重新绑定保留的原页面端口，并更新观察绑定标识。已有 observer 只请求一次合并的只读状态刷新；相同绑定重复安装不增加扫描，不增加监听器或轮询。旧弹窗与旧绑定的迟到事件不能改变恢复页面的忙碌或上传状态。

网络传输服务只在新预连接准备处检查压力。已打开环境和正在进行的连接不会因本策略关闭。不存在新的自动销毁会话、杀进程、清数据、驱逐环境或重发任务路径。

## 原生能力范围

构建输入固定为官方 Firefox 157.0.1、上游 revision `737ec77d798755890b062aab541a90d6c75afd19`，对应 `org.mozilla.geckoview:geckoview:157.0.20261005135250`，输入 AAR SHA-256 为 `15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268`。当前候选运行时使用独立坐标 `local.pocketchat.sdk:geckoview-caret:157.0.20261005135250-pocket1`，派生 AAR SHA-256 为 `ede7935705aff417b9f5af0470f553ea55672680419bc61e9a49f64192cd4876`，不冒充未修改的官方 AAR。

补丁与源码保存在 `third-party/gecko/`，`tools/gecko/build_caret_sdk.py` 从源码编译后仅替换 `org/mozilla/geckoview/GeckoEditable.class`。已完成的 AAR 条目比对确认其他 SDK 类、原生库与资源字节不变；没有加入 SDK 输入观察器。源码、补丁、配方、构建输入和产物哈希由 `third-party/sdk/geckoview-157.0.1-editable-selection.json` 记录，实际 CI 构建还须绑定干净源码、run/attempt、解析到的运行时依赖及 APK 字节。

输入改动限于一次 action 内恰好提交一个非修饰合成 key-down、无 span 且非 surrogate 的单字符、原 action 与 shadow 选区均折叠，并且 shadow 光标已位于该字符之后的路径。该路径保留原生当前光标；显式选区、组合输入及原有回退判据仍保留。Java 提交调用正常返回不被当作原生已接受输入的回执。这项单类改动的 Android 行为尚未验收，也未扩大为百度输入法全部路径的修复声明。

`NativeCapabilityManifest` 与 `third-party/sdk/identity-capabilities.json` 仍明确标记独立时区、Canvas、WebGL、音频和字体的自定义原生控制为不支持。输入补丁不新增这些能力，既有官方隐私 API 不被改名为新能力。

`EnvironmentResourcePolicy.admit` 的测量预算模型仍未接到生产容量限制。未知可用内存不能提出暂停建议；未测量的容量不写成“八环境通过”。启动检查点读取完成不是最新网页状态落盘回执，SDK `flushSessionState` 也不提供可用于安全驱逐的同步确认，因此本版不依据它们销毁网页。

## 验证与证据

- JVM 直接执行生产压力采样/决策代码；Android API 为明确 doubles。完整来源、源码哈希与唯一断言保存为 `resource-pressure-host-results.json`。
- JSDOM 执行真实 observer 模块，验证相关变化节流、序列与旧手势兼容，并验证大量无关文本/list 变化不增加资源扫描。它是受控 DOM 检查，不能作为实际帧率提升证据。
- `ResourcePressureIntegrationActivity` 在独立测试进程使用候选 SDK 和生产桥接，检查冷低内存零次 runtime 创建、任务恢复优先、同一候选实际加载、旧期限围栏、保留会话、受控网页状态、重复附件记账与弹窗返回；随后保留继承的 129 项 SDK 上下文和 9 项真实闭锁请求检查，共 174 项。低内存输入及恢复任务明确为合成控制；Android MemoryInfo 和当前应用 PID PSS 为实际观察，排除 Gecko 子进程。
- 弹窗验证直接调用生产导航 delegate，实际打开、加载并关闭 SDK 会话；读取实际文档 observer 字节后原样交给资源判断，核对绑定、代次、文档、序列、草稿、Cookie 标记与发送计数。它使用受控 loopback 页面和显式测试适配，不能宣称真实 ChatGPT 登录、扩展消息交付或物理用户点击已经通过。
- 原 burst 输入测试的驱动、步骤、时序与断言不变，另有 `GeckoCaretCompatibilityIntegrationActivity` 的 14 项受控编辑场景，覆盖快速光标移动、选区替换、删除、撤销、多字提交、粘贴、中文组合与结束组合、批量提交、反向选区、拒绝输入、软键盘单字符、码点删除及空组合。这些场景调用原始 InputConnection 与 Android 输入路径，记录实际草稿、选区和事件；当前候选尚未执行这些 Android 检查，不能写为通过。
- Android 原始报告、已安装 APK 字节/构建标记、调用 nonce、完整断言与当前源码绑定；原 burst、新增编辑检查、资源 174 项、原 1.6 模型/意图和 1.7 模板 181 项与共享闭锁 9 项必须在当前候选同一已安装集成 APK 上独立通过。构建记录和主机检查不能代替实际 Android 结果；旧失败运行保留原样，不计入候选验收。

当前候选的受控 Android 门禁仍待执行与通过。资源诊断不是物理 ARM 手机容量、真实 ChatGPT 上传、文件选择手势、百度输入法全部输入路径、下载吞吐、登录保持或长时间后台恢复验收。本版不声称实际帧率、网络延迟改善或物理手机最多可运行几环境。候选包通过云端检查后，正式发布仍要求用户真机清单。

## 官方 SDK 的桌面 UA 范围

桌面环境的页面、iframe、Worker JavaScript 与四类文档/脚本/页面 fetch 请求头使用实际 session UA。两类 Worker fetch 请求头仍按独立 `GeckoSession.getDefaultUserAgent()` 的 SDK 移动默认值核对；实际不一致保留在原始报告中。静态 getter 不表示运行时已确认，也不是完整桌面 UA 或指纹验收。本版没有修改 Worker 请求头或实现 WebRequest 修复。

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
