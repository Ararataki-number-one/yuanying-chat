# 2.0.40 公开开发交接

当前正式版为 **2.0.40 / versionCode 93**。标签 [v2.0.40-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.40-gecko) 对应源码 `7e8b235cee0a406c04ff9c914b790cd13cbcc727`，源码树为 `a135f6cd81a028be3c1c0f9b727d006a963e637e`。详见 [发布说明](RELEASE-v2.0.40.md)；原签名正式包可覆盖升级。

本版在页面导航或线路归属失效时，取消普通文档检查的原生任务，由已有工作线程处理连接断开。旧检查回调不再更新新页面结果；独立身份检查和服务检查保留各自生命周期。回复、待确认发送、附件、上传与下载期间的保护条件继续保留。原有延迟看门狗仍在队列中，过期后由代次检查阻止生效；本版没有移除该回调。继续保留单 GeckoView、ChatGPT 原网页、独立环境、固定出口、登录与草稿。

## 已核验的发布证据

- [主验收 41014965975 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41014965975)、[Profile 41014965949 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41014965949)、[Mihomo 41014965953 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41014965953)：共 14 个实际任务通过；原有 10 项 CI 校验与本地重放均通过，9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项界面截图通过。不同批次的证据不混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.40-gecko-arm64.apk`，119357093 字节，SHA-256 为 `22a0842a33fa8c73f1b708fd439575d3cef466d2d5adb0f1cbae38f298e64505`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `83c243cb74832684c9fe10b7cb84261a8acc71d8`，树 `3e948a0419b36e1f61d0edcb72892af7894b8fb8`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `6a63efb1e78b92522fb0b33b3a2ba5529469c5f5`，公开树 `a90c765ef36983b186ee13e184c9948ad04ae02c`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 41056602979 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41056602979) 的 8 个步骤均通过；匿名完整 APK、原签名、SDK 来源、源码标签与更新入口核验通过。公开验收回执 SHA-256 为 `a2ae26c40335ed92fa9bb32b766e6c243148f8ad5bb65571f84853d766172b4b`；发布 manifest SHA-256 为 `fa67c5fe7d9cf0983da3c6cc4161dec70fa2e946921166a0d11112dd1c2dce07`；实际 REST 标签响应 SHA-256 为 `037ba4edb94210d849c688c029b3d2bcceb45e5c61da116f9f47aa123d88a836`。

## 尚未验证与后续

此前不合格批次及原始失败记录继续保留，不与当前源码与批次的完整成功证据混用。当前基线继承已核对的 CI 诊断导出边界，原有隐私扫描和业务验收保持不变；早前拒绝原文件的字段与类别仍未确认。实际连接断开时限、手机内存、电池与速度变化仍待测量，不承诺固定的多环境运行容量。

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.41 / 94**，按既定计划提供有界加密环境配置导入导出；只包含允许的配置，不包含登录、Cookie、网络凭据或环境密钥。后续版本源码或 CI 完成不代表已经发布；每版以正式 Release 与实际验证记录为准。

此前已发布说明与交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
