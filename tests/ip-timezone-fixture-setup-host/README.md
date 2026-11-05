# IP 时区测试启动边界

`run.py --java-home <JDK17> --json-jar <actual-json.jar> --output <report.json>` 直接编译当前完整的 `IpTimeZoneFixtureApplication`、`IpTimeZoneFixtureScopes`、`GeckoIpTimeZoneEvidenceProvider`，以及当前完整的时区 Spec、Policy、严格 JSON 和进程归属策略。父 Application 的 attach/onCreate/profile、Profiles 的进程/上下文/prepare 方法和 Environment Identity 从当前源码逐字提取。

检查覆盖明确声明的 generic 手动系统基线、所有已持久化字节保留、重入与应用 monitor、真实文件的 marker/叶节点软链接、provisional/reserved/armed 生命周期、安装身份/nonce/时间/槽位绑定、UID 2000 固定读口、并发 prepare/clear 的串行化，以及身份和 CAS 变化。另编译执行七个语义反例，要求原断言拒绝。

Android 生命周期、bootstrap 回调、metadata、时钟、Binder、AtomicFile、catalog、vault 和时区 Store 均是明确的宿主协作者。这里不运行 Android、不运行 Gecko，也不读取真实密封配置、不验证原生时区、网络或网页效果。缺记录默认值使用当前真实 `GeckoTimeZoneSpec.automatic()`；真实 MainActivity 首次加载及实际 Store/SDK/线路行为由独立 Android gate 验证。

桌面 JSON 和 Android JSON 各运行一次，报告记录完整输入哈希、提取方法哈希、所用 JSON JAR 和运行期源码稳定性。宿主通过不能替代实际 Android 诊断或发布验收。
