# 2.0.44 公开开发交接

当前正式版为 **2.0.44 / versionCode 97**。标签 [v2.0.44-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.44-gecko) 对应源码 `a03238be99c9a2dee5802c03b1e5bb7d59f11ddc`，源码树为 `a63de59b7bc1be6b03d68c2cb98b847306bb5d71`。详见 [发布说明](RELEASE-v2.0.44.md)；原签名正式包可覆盖升级。

本版在请求结果、高级说明和服务摘要中明确 Shared Worker、Service Worker 的覆盖边界，保留 Dedicated Worker 的既有对照。检测服务可声明是否支持相关检测，缺少声明时显示未知；声明仅为服务自述，客户端始终标明尚未覆盖。本版没有新增 Shared Worker 或 Service Worker 探针、脚本端点、注册或清理操作，也不把服务声明视为保护通过。继续保留单 GeckoView、ChatGPT 原网页、独立环境、固定出口、登录与草稿。

## 已核验的发布证据

- [主验收 41071087899 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41071087899)、[Profile 41071087900 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41071087900)、[Mihomo 41071087907 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41071087907)：共 14 个实际任务通过；原有 10 项 CI 校验与本地重放均通过，9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项界面截图通过。不同批次的证据不混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.44-gecko-arm64.apk`，119369381 字节，SHA-256 为 `8cf48a8684c940bf61fc4ddd2140a755b634e20bb1b35fd524553be52c0849d2`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `5c37a5f936b34edb91eedec9dd42d037e50ebb75`，树 `db511b21d7cc43bf2b2be02c63bacc5e76614390`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `db4b7f4762d67021ad45bab14916372cd95198e6`，公开树 `fc3b3240a70930d1653828cf0920660820e043ba`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 41079134420 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41079134420) 的 8 个步骤均通过；匿名完整 APK、原签名、SDK 来源、源码标签与更新入口核验通过。公开验收回执 SHA-256 为 `0d16f6571e8f8f399531f65c149b56dcdd0a2d9158f2013c2432a9d95f302ce4`；发布 manifest SHA-256 为 `b773caadaa0e198424d0fa04430e5926d3599c0e5a980d80144c3ad067f41ce5`；实际 REST 标签响应 SHA-256 为 `a15685bd70bdb0a1430c50e4d2cb979ecf04db48fdfb8a814f04dc197600cad6`。

## 尚未验证与后续

此前不合格批次及原始失败记录继续保留，不与当前源码与批次的完整成功证据混用。当前基线继承已核对的 CI 诊断导出边界，原有隐私扫描和业务验收保持不变；早前拒绝原文件的字段与类别仍未确认。当前源码树沿用此前候选的全部应用、测试与工作流字节。本次完整验收属于单次有限确认；先前输入样本拒绝及其原因未知的原始记录继续保留，不描述为功能修复。Shared Worker 与 Service Worker 的真实请求、缓存和生命周期仍未检查，不能据此判断官网使用了哪些 Worker 或手机上的保护效果。

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.45 / 98**，按既定计划收紧自检诊断复制内容，只复制白名单中的有界状态、数字和合法哈希；保留本机原始结果查看用途。后续版本源码或 CI 完成不代表已经发布；每版以正式 Release 与实际验证记录为准。用户新增的后续范围为：2.0.45 正式完成后，以该实际正式源码为基线，在同一分支把八项体验需求整合为一次 2.0.46；手机验收通过后才正式发布 2.0.46。当前只读规划和受控检查不构成手机验收。

此前已发布说明与交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
