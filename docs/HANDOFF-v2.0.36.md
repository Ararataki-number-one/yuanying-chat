# 2.0.36 公开开发交接

当前正式版为 **2.0.36 / versionCode 89**。标签 [v2.0.36-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.36-gecko) 对应源码 `26d94c764b6dee40c1dea5ed2ea182101ea61e95`，源码树为 `a66fa5cbc5f7c606fb63b2983105cfb66f504659`。详见 [发布说明](RELEASE-v2.0.36.md)；原签名正式包可覆盖升级。

本版在回复正文预热执行前检查原提问是否仍属于当前文档，且其后没有新提问；过期任务跳过旧正文读取与转换。正常回复、加载历史和无关侧栏变化沿用既有逻辑与阅读位置保护。有效长回复仍按原有同步路径转换，尚未按 CPU 时间预算切片。继续保留单 GeckoView、ChatGPT 原网页、独立环境、固定出口、登录与草稿，不移动视口或重发聊天。

## 已核验的发布证据

- [主验收 40995230491 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40995230491)、[Profile 40995230581 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40995230581)、[Mihomo 40995230476 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40995230476)：共 14 个实际任务通过；原有 10 项 CI 校验与本地重放均通过，9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项界面截图通过。不同批次的证据不混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.36-gecko-arm64.apk`，119348901 字节，SHA-256 为 `623af278233cc59c830e0616bf25f695e0e997eb7265438376a0aee9d56d96fa`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `318d3410ed5d916161c47112bded2762adb112ce`，树 `01297417ddffa74032e0fb78e4126bada61da70b`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `68a62d43a3158293cfb436208404335622cb5e9f`，公开树 `f1fd07aaf3fe4522749fb0e46afc2f515f3dec5e`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 41003648431 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41003648431) 的 8 个步骤均通过；匿名完整 APK、原签名、SDK 来源、源码标签与更新入口核验通过。公开验收回执 SHA-256 为 `623489add3831067eb688efa84b20033e801cf901db4cd677f699abcc0e5651f`；发布 manifest SHA-256 为 `16dbf7714cbb94c6404fee5f43ebb7f84d88c1b3d9b650d0ff0d62ba6697a734`；实际 REST 标签响应 SHA-256 为 `3065eff265bcbdfa81c3b182a9e081d934669592f8805aeb7038955829e9d9c8`。

## 尚未验证与后续

此前版本不合格批次及原始失败记录继续保留，不与当前源码与批次的完整成功证据混用。受控主机中的工作量减少不能代替手机帧率或流畅度验收。

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.37 / 90**，按既定计划继续处理取消后尚未交付的上传副本与存储占用反馈。后续版本源码或 CI 完成不代表已经发布；每版以正式 Release 与实际验证记录为准。

此前已发布说明与交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
