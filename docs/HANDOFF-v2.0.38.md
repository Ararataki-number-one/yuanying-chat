# 2.0.38 公开开发交接

当前正式版为 **2.0.38 / versionCode 91**。标签 [v2.0.38-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.38-gecko) 对应源码 `4df73b636b96eedebe5247478fabb5f736e5b3c0`，源码树为 `f69d9b0caed9135d474f1ffb93ee670be823befa`。详见 [发布说明](RELEASE-v2.0.38.md)；原签名正式包可覆盖升级。

本版每次刷新通过一次只读复合查询取得下载列表展示记录，复用结果映射与未变化的行内容。行操作使用最新任务对象；读取失败时保留最近确认的列表、筛选与滚动位置，提供行内重试。环境名称、语言、时区和状态颜色变化仍更新相应内容；保存、恢复、删除和线路保护沿用既有规则。历史仍全量读取，所有卡片仍附着，尚未分页或虚拟化。继续保留单 GeckoView、ChatGPT 原网页、独立环境、固定出口、登录与草稿。

## 已核验的发布证据

- [主验收 41010493735 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41010493735)、[Profile 41010493551 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41010493551)、[Mihomo 41010493552 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41010493552)：共 14 个实际任务通过；原有 10 项 CI 校验与本地重放均通过，9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项界面截图通过。不同批次的证据不混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.38-gecko-arm64.apk`，119357093 字节，SHA-256 为 `2e810189f1fc4565fdeadd851ac9f8be3a8c1ea4337e75e5577c9c1a7e25a374`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `31e40c926292175e1036add5b70827cbe09f9570`，树 `7449c495718cd5abef0fd0086917bc671467423d`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `35661544b139e4f537988a7eb26dc8031f1a3849`，公开树 `f59d886cbdb5fa64934294843a969444d2ba7190`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 41015564769 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41015564769) 的 8 个步骤均通过；匿名完整 APK、原签名、SDK 来源、源码标签与更新入口核验通过。公开验收回执 SHA-256 为 `728edc50d2d78b1f913c25a6f7ad4aedf0dba5dbde074a0f11fe40b9e93dd358`；发布 manifest SHA-256 为 `e2fc0775ab7ad4449f1d679324510e088139c79606a7637c535e75a0730dd9ac`；实际 REST 标签响应 SHA-256 为 `0e55c0fac9d87d4226a23355b1458d87272c171ad0b0ef1246f79c59816ac790`。

## 尚未验证与后续

此前不合格批次及原始失败记录继续保留，不与当前源码与批次的完整成功证据混用。本版同时收紧 CI 诊断报告导出边界，原有隐私扫描和业务验收保持不变。此前被拒绝原文件的字段与类别仍未确认；本次成功不能解释原触发原因，也不能据此归因于应用网络或并行调度。下载查询与绑定次数减少不等于手机耗时已改善，Android 数据库、长列表布局和真机流畅度仍待验收。

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.39 / 92**，按既定计划补齐网页反复退出、自动恢复额度耗尽后的前台提示，不增加失败处理、网络重试或聊天重发。后续版本源码或 CI 完成不代表已经发布；每版以正式 Release 与实际验证记录为准。

此前已发布说明与交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
