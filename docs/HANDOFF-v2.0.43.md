# 2.0.43 公开开发交接

当前正式版为 **2.0.43 / versionCode 96**。标签 [v2.0.43-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.43-gecko) 对应源码 `532882c31f91ef5945c3951bab12be4801eb26c6`，源码树为 `244f3fd0f41cefa3bd02b0dc257f57753b207a71`。详见 [发布说明](RELEASE-v2.0.43.md)；原签名正式包可覆盖升级。

本版在本机自检和指纹模板高级详情中，按需读取七项 Gecko SDK 运行配置。区分已读到的设置值、沿用默认但未观测的值，以及暂未取得的值；可空结果显示未知，不当作关闭。观测关联当前环境、运行实例与配置版本，过期结果不更新基线。全部读取均为只读操作，不增加设置开关、轮询或内核重启。继续保留单 GeckoView、ChatGPT 原网页、独立环境、固定出口、登录与草稿。

## 已核验的发布证据

- [主验收 41061028028 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41061028028)、[Profile 41061027943 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41061027943)、[Mihomo 41061027920 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41061027920)：共 14 个实际任务通过；原有 10 项 CI 校验与本地重放均通过，9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项界面截图通过。不同批次的证据不混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.43-gecko-arm64.apk`，119369381 字节，SHA-256 为 `ce7c7501d1fc0be5061199b775887ee461b110a0e999e82123f0c25f63c789ad`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `3e2633dfbfa7beb02d6a0e687265c184e536f9ce`，树 `0a8e29db40df7901ee6ec873571652acae85f8ff`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `c81660546efae6656d96d5544d453b0ab283cc1c`，公开树 `7f304bcdc11253e2e568db18f177241a2a6165eb`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 41068279301 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41068279301) 的 8 个步骤均通过；匿名完整 APK、原签名、SDK 来源、源码标签与更新入口核验通过。公开验收回执 SHA-256 为 `af85dbb1d8dbe1173b4c5c7e5e69e69b78af456cd52bacc7d7ae09c9ead7a295`；发布 manifest SHA-256 为 `5500e2c9c260c95916b14ef2e96517bea973460bb0ccb7412eb60fbe2a5e258b`；实际 REST 标签响应 SHA-256 为 `6f6c87564265bf46b7c897bdb3313e22637be3b098b24b7d2ecfd8e4bc72d06c`。

## 尚未验证与后续

此前不合格批次及原始失败记录继续保留，不与当前源码与批次的完整成功证据混用。当前基线继承已核对的 CI 诊断导出边界，原有隐私扫描和业务验收保持不变；早前拒绝原文件的字段与类别仍未确认。本版补齐旧主机测试模板缺少的一个运行状态字段，属于 CI 适配，应用代码与原有 Python 校验、断言和固定摘要保持原样。这些 SDK 设置对象读数不能替代渲染进程、跨站进程或存储分区证据，也不构成独立抗指纹控制。真实手机上的保护效果和性能仍待验证。

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.44 / 97**，按既定计划明确 Shared Worker 与 Service Worker 的检测边界；服务支持声明仅为自述，客户端仍标明尚未覆盖。后续版本源码或 CI 完成不代表已经发布；每版以正式 Release 与实际验证记录为准。

此前已发布说明与交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
