# 1.6、1.7、2.0 分版本合并与验收

基线是正式发布标签 `v1.5.21-gecko`，源码提交
`a6c60f38fa51c107706626bae6707d2bd317c803`。开发默认分支仍落后这个标签，
请先把待合并分支建立在这个标签上，避免用旧 1.5.0 代码覆盖新版功能。

三个版本是按依赖排列的候选代码，不是三个已发布 APK。版本建议为
1.6.0/code48 → 1.7.0/code49 → 2.0.0/code50；若发布通道已经使用这些
versionCode，发布前应增加到比当前安装包和更新通道更高的唯一编号。

## 合并顺序

1. 先审查 1.6：网络状态、独立出口订阅、环境身份与配置迁移。
2. 在 1.6 上审查 1.7：原生模板、语言、UA/视口一致性和分上下文自检。
3. 在 1.7 上审查 2.0：能力清单、资源保护策略、证据和维护工具。

分版本补丁必须按顺序应用到基线，不可把 2.0 单独应用到 1.5.21。
本工作不合并主分支、不替换已发布标签、不改变原签名、不发布安装包。
Git bundle/patch 由交付脚本生成，附 SHA-256 和文件清单。

## 共同产品边界

- GeckoView 是唯一内核，ChatGPT 官方网页负责输入、模型、历史和聊天。
- 网络只服务应用；入口与出口订阅独立，固定出口不会自动轮换。
- 正常切换、保存和前台完成保持安静；后台完成提醒仍须主动开启。
- 旧登录目录、Cookie、草稿、下载、槽位和 Keystore 别名继续沿用。
- 希望值、内核确认值、网页观测分别记录；设置保存不等于指纹生效。

## 1.6 验收

参见 `IMPLEMENTATION-v1.6-ENVIRONMENTS.md` 和
`IMPLEMENTATION-v1.6-SUBSCRIPTIONS.md`。

- 更新订阅失败保留旧有效快照；同名节点、重排、凭据变化有明确身份。
- 删除正在被环境或待应用候选引用的出口来源被拒绝。
- 刷新出口库不改变现有线路，应用时再次核对来源/节点/修订号。
- 相同已验证线路遇到 ipify 故障保持可用；新线路、进程变化和出口不符仍阻断。
- gstatic 故障且 ChatGPT HTTP 可达时不切入口、不停止健康会话。
- 忙碌回复、上传、下载期间不执行线路探测或自动切换。
- schema6 升级 schema7、默认槽删除后重建、旧回调与新身份隔离。

## 1.7 验收

参见 `IMPLEMENTATION-v1.7.md`。逐项验证实际 Gecko 请求头、页面主执行
环境、同源 iframe 与 Dedicated Worker。跨源 iframe、Shared Worker、
Service Worker 尚未覆盖时明确显示未覆盖，不计为验证通过。

原生语言设置需要验证 Accept-Language、navigator.languages、Intl 与
多环境独立性。强化 RFP 单独测试登录、上传、下载、工具、音视频和时区
标准化；主执行环境采样属于网页可影响的观测，不能当作防篡改证据。

## 2.0 验收

参见 `IMPLEMENTATION-v2.0.md`。官方 SDK 阶段提供可工作的能力清单与
资源决策/维护框架，独立时区、Canvas/WebGL/音频/字体自定义原生控制
目前没有实现。可选原生原型报告与设备预算不会自动启用后端。

需要原生补丁时：先实现单字段原型，再完成 ARM 构建、跨上下文一致性、
环境隔离、ChatGPT 兼容性、一次上游升级合并及降级演练后决定纳入发布。
资源策略不强制退出活动环境；进程回收须等待最新检查点持久化回执。

## 测试与发布

1. 用 JDK 17+ 执行主机测试。环境模型的 JVM 测试需 JSON-java jar；
   jar 只用于主机测试，生产继续用 Android org.json。
主机测试命令：`python3 tools/gecko/run_profile_host_checks.py --json-jar /path/to/json.jar`；
2.0 追加 `bash tools/gecko/run_identity_host_checks.sh`。新增 Android 夹具使用
`python3 tests/gecko/run_profile_features.py --adb /path/to/adb --serial DEVICE`，
只清理固定的 `.test` 合成包，不接受正式包名。

2. 按 BUILD.md 用固定官方 SDK/Gradle 进行完整 APK 编译和 lint。
3. 用 Android ARM 真机执行新增和既有集成测试，验证真实账户登录。
4. 同一手机/网络/操作分别统计冷加载、热加载、页面可用 p50/p95、断开
   次数、恢复时间、输入延迟和资源占用。人工代理等待不代表公网收益。
5. 原证书签名、递增 versionCode、相同包名，测试包和测试端点不进入正式包。
6. 构建、源码、测试报告、发布清单必须来自同一候选；本次主机测试不
   替代 Android、官方 AAR 编译、ARM、真实 Google 登录或长期耗电验收。

当前云环境没有 Android SDK/设备。可执行 Java 源码编译使用从已发布
1.5.21 APK 提取的接口类和 Android API35 jar，是编译兼容性检查。
这些临时依赖不进入源码、APK、Git bundle 或正式构建；官方 AAR 不作任何变换。
