# 2.0.41 公开开发交接

当前正式版为 **2.0.41 / versionCode 94**。标签 [v2.0.41-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.41-gecko) 对应源码 `e99acdb873d4c44f303c0d97abf9c2c1fa281c30`，源码树为 `12f91afcb24b842a371ad8cdb663ff7af04c7b48`。详见 [发布说明](RELEASE-v2.0.41.md)；原签名正式包可覆盖升级。

本版增加环境配置的密码加密导出与导入。范围限于环境名称、浏览器模板、语言顺序和七项布尔偏好，采用 AES-GCM 完整性校验及 PBKDF2 密钥派生；密钥派生与文件处理在工作线程执行。登录、Cookie、聊天、草稿、附件、订阅、网络凭据、固定出口和来源环境身份不在备份中。确认导入后创建新的未使用环境，网络保持未配置并要求外部 VPN，不覆盖已有环境或自动打开网页。提交结果不明时显示待确认，只清理归属明确且尚未使用的暂存记录。继续保留单 GeckoView、ChatGPT 原网页、独立环境、固定出口、登录与草稿。

## 已核验的发布证据

- [主验收 41016867809 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41016867809)、[Profile 41016867801 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41016867801)、[Mihomo 41016867834 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41016867834)：共 14 个实际任务通过；原有 10 项 CI 校验与本地重放均通过，9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项界面截图通过。不同批次的证据不混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.41-gecko-arm64.apk`，119365285 字节，SHA-256 为 `916009f8704f6e33c3886a759a152a2da4fe288ec3855c03e64ec892652d1f8e`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `e82e3bed01f7e4d870fd4f2ad39c4865f2eeb053`，树 `468ad2304ab451b8a4d49d90f1f75836b04743d5`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `4c3ff5bc0d3ccc8535cf94ec87b78d7efc2f942c`，公开树 `fca9b18a275c4fd01eb02f007148729c97503329`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 41058580438 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41058580438) 的 8 个步骤均通过；匿名完整 APK、原签名、SDK 来源、源码标签与更新入口核验通过。公开验收回执 SHA-256 为 `25640a4154f0d541060206175be2931f0f9c2b9aa15b1d06918c5cbfda89be23`；发布 manifest SHA-256 为 `f6b83da5f4cfefc23fc030e757629b9dd1b4f2f7b3bdf37ec4274e508958ef60`；实际 REST 标签响应 SHA-256 为 `6cb1cd400140aec39d833e685cfb3ff59ff0ff1edfd43f7b0eab51a6ae14a60f`。

## 尚未验证与后续

此前不合格批次及原始失败记录继续保留，不与当前源码与批次的完整成功证据混用。当前基线继承已核对的 CI 诊断导出边界，原有隐私扫描和业务验收保持不变；早前拒绝原文件的字段与类别仍未确认。真实 Android Keystore、系统文档提供者、手机覆盖升级以及导入导出的现场体验仍待验证。

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.42 / 95**，按既定计划清理页面切换后的旧通信任务，拒绝过期端口消息及其新任务派发；不增加刷新或自动重发。后续版本源码或 CI 完成不代表已经发布；每版以正式 Release 与实际验证记录为准。

此前已发布说明与交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
