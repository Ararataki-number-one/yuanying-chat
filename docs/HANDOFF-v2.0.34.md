# 2.0.34 公开开发交接

当前正式版为 **2.0.34 / versionCode 87**。标签 [v2.0.34-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.34-gecko) 对应源码 `7d0cf34eea4f744c4f18aaaa5492db9d0a9799db`，源码树为 `78b2a3a6b4ffeedb60a2d6f776a53b31172c73b4`。详见 [发布说明](RELEASE-v2.0.34.md)；原签名正式包可覆盖升级。

连接状态面板区分线路与恢复进度、当前网页最近观测到的状态和本机待确认发送。环境、会话或文档变化后，旧面板操作失效；不自动重发聊天、不自动直连、不改变固定出口。继续保留单 GeckoView、ChatGPT 原网页、独立环境、登录与草稿。

## 已核验的发布证据

- [主验收 40978643528 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40978643528)、[Profile 40978643515 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40978643515)、[Mihomo 40978643533 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40978643533)：共 14 个实际任务通过。原有 10 项校验和本地重放均通过；附加的 9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项当前界面截图均为受控验证。早前失败批次保留，不与本次完整成功批次混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.34-gecko-arm64.apk`，119344805 字节，SHA-256 为 `baca12938270ba799fc58c69d2152cd0b5c4f1019acf63334413e24716f83eff`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `230df3bb7661f5c46ed5438e0b935da6667e2ff6`，树 `47a6cda591a4510481b59cbec5cfeb59c08d7697`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `64b8e20788f6e774d0e9c06375f0a14a00f5a8b3`，公开树 `b5363edbfcd6757f4d9b2e3d42f9e63e926543d8`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 40985411395 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40985411395) 的 8 个步骤均通过；已保留首次空结果及随后观察到的实际任务记录。
- 匿名完整 APK、原签名、SDK 来源、源码标签和更新入口均核验通过。公开验收回执 SHA-256 为 `ea91ecd2e7056d03eb4c4e02c6b2bdea9dca0f63b7bd0639bd4fa6215c9c11fd`；发布 manifest SHA-256 为 `533a4324ef6e6ed420fba0a97164ee438d50042f8167804da5ed8a57bb233ccd`；实际 REST 标签响应 SHA-256 为 `302ed0fd8529ffc928494fe2880c2cbed538f6c5cfcd0be94225f0c017247f16`。

## 尚未验证与后续

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认实际手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.35 / 88**，按既定计划继续输入与草稿边界优化。后续版本的源码准备或 CI 执行不代表已经发布；每版均以对应正式 Release 和实际验证记录为准。

2.0.32、2.0.33 的已发布说明和交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
