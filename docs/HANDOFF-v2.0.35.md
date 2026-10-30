# 2.0.35 公开开发交接

当前正式版为 **2.0.35 / versionCode 88**。标签 [v2.0.35-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.35-gecko) 对应源码 `e3157193d460f9200ae14aa81bebe2bcd387b899`，源码树为 `58c87b5e8bceea91cef2a0cbf38924c00a268dd6`。详见 [发布说明](RELEASE-v2.0.35.md)；原签名正式包可覆盖升级。

本版完善可选本地草稿策略、受支持文本结构中的有界 UTF-16 选区与选择方向恢复。输入或组合输入已经更新时，过期恢复任务失效；无法可靠映射的富文本结构保留当前选区。不增加自动聚焦、发送或刷新。继续保留单 GeckoView、ChatGPT 原网页、独立环境、固定出口、登录与草稿。

## 已核验的发布证据

- [主验收 40991163228 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40991163228)、[Profile 40991163159 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40991163159)、[Mihomo 40991163197 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40991163197)：共 14 个实际任务通过；原有 10 项 CI 校验与本地重放均通过，9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项界面截图通过。不同批次的证据不混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.35-gecko-arm64.apk`，119348901 字节，SHA-256 为 `3546bb06fa75cef108772c65a3e3e09ad5895402de6eb0c11942659d99e13186`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `5721d18a73701290e14db1dbd1b8f983d6ed52ba`，树 `5b1df3e0ac2e43c072422836d522853b00c0efe1`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `80f2975e392f87cd34235aaa0832baee61d7823f`，公开树 `587959650b395588bdcaaf528b7ec47cbc8df7d7`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 41002565331 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41002565331) 的 8 个步骤均通过；匿名完整 APK、原签名、SDK 来源、源码标签与更新入口核验通过。公开验收回执 SHA-256 为 `1183d55c69038d4ced615e43eda2d1ca5c777e164f888260bd38ac3044e9255b`；发布 manifest SHA-256 为 `16879d51ac0c80238fd3268aac37c394e588ac14a78b0dacecc99f094ff3104b`；实际 REST 标签响应 SHA-256 为 `8693a21f523af5c3329132af5eb4c83df5aa8701da4accc0ba2f161d12d68e81`。

## 尚未验证与后续

早前不合格批次及原始失败记录继续保留。本次同源码、全新批次的完整通过不能解释旧输入样本或手势失败的原因，也不能证明其原因已修复。

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.36 / 89**，按既定计划继续减少过期回复采集任务的无效工作。后续版本源码或 CI 完成不代表已经发布；每版以正式 Release 与实际验证记录为准。

此前已发布说明与交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
