# 2.0.42 公开开发交接

当前正式版为 **2.0.42 / versionCode 95**。标签 [v2.0.42-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.42-gecko) 对应源码 `b25974a69d6c8d6a7652f3c55455d2f6cccd5da7`，源码树为 `2b2dc1ee24305e020222941f96f851e365af4d62`。详见 [发布说明](RELEASE-v2.0.42.md)；原签名正式包可覆盖升级。

本版在确认文档切换后，先标记旧端口失效，再取消所属回调；拒绝过期页面端口的传入消息，停止向其派发新的网页求值与环境检查。其他会话和新文档的任务继续保留。沿用顶层页面限制、线路保护、未知动作拒绝及既有字符数量限制，不增加刷新或自动重发。普通网页求值结果仍没有统一的传输大小上限。继续保留单 GeckoView、ChatGPT 原网页、独立环境、固定出口、登录与草稿。

## 已核验的发布证据

- [主验收 41057219146 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41057219146)、[Profile 41057219224 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41057219224)、[Mihomo 41057219110 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41057219110)：共 14 个实际任务通过；原有 10 项 CI 校验与本地重放均通过，9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项界面截图通过。不同批次的证据不混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.42-gecko-arm64.apk`，119365285 字节，SHA-256 为 `c78699b0f5fbffa0b9446c2df7fef4e041a4a8b7d829314bdbbc3c3df3098e32`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `7928d4e05699142507745106ef032297428145dd`，树 `25e570db1374ce07438aa738fb0f2c1a3363f477`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `e628ce617b5bd2726b552a3e788ef66a5197ccf1`，公开树 `290e6125701dfebd80a876355a23371db3745d3a`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 41063985682 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41063985682) 的 8 个步骤均通过；匿名完整 APK、原签名、SDK 来源、源码标签与更新入口核验通过。公开验收回执 SHA-256 为 `229e813902200198514b104c442f4f142fc59a0edcff9e52e530f457a957731d`；发布 manifest SHA-256 为 `9c38c4ca692601a5677a53b5376003c69d466f6c7c7448eda3621fa30b57fb46`；实际 REST 标签响应 SHA-256 为 `a1c9e7918d1c2015599bc2d43d0e6eb98e43027fd14cad91c4df84db84b15dbf`。

## 尚未验证与后续

此前不合格批次及原始失败记录继续保留，不与当前源码与批次的完整成功证据混用。当前基线继承已核对的 CI 诊断导出边界，原有隐私扫描和业务验收保持不变；早前拒绝原文件的字段与类别仍未确认。本版的六处 CI／兼容性调整仅补齐有界历史输入与对应旧工作流的精确逆变换校验，没有改变应用行为或证明手机提速。真实 Gecko 事件顺序、全部桥接与权限边界及手机效果仍待验证。

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.43 / 96**，按既定计划读取现有 SDK 的只读运行状态；未知值明确保留为未知，不新增控制、轮询或自动重启。后续版本源码或 CI 完成不代表已经发布；每版以正式 Release 与实际验证记录为准。

此前已发布说明与交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
