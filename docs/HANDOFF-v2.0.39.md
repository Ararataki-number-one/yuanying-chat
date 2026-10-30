# 2.0.39 公开开发交接

当前正式版为 **2.0.39 / versionCode 92**。标签 [v2.0.39-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.39-gecko) 对应源码 `6c8252ff997071df5bf845fb429f2acf4443665d`，源码树为 `7826ebba3d5847bb458a9d7b7d3879f45720adce`。详见 [发布说明](RELEASE-v2.0.39.md)；原签名正式包可覆盖升级。

本版在网页进程于后台退出、自动恢复额度耗尽且没有已有错误说明时，返回前台显示“网页多次退出，自动恢复已暂停；请检查连接后点按重新加载”。恢复额度、时间窗口、手动重载和已有独立网络重试沿用原有规则。新增分支只更新提示与状态，不额外调用失败处理、导航结束、网络重试或聊天重发。继续保留单 GeckoView、ChatGPT 原网页、独立环境、固定出口、登录与草稿。

## 已核验的发布证据

- [主验收 41011731844 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41011731844)、[Profile 41011731810 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41011731810)、[Mihomo 41011731807 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41011731807)：共 14 个实际任务通过；原有 10 项 CI 校验与本地重放均通过，9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项界面截图通过。不同批次的证据不混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.39-gecko-arm64.apk`，119357093 字节，SHA-256 为 `16e7a2e756e3d4647075b9a449655ef70760753ca3fb27a4d670582b34950699`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `69b6c3e3a14de276b6b5cc12d29cd69d7e01f00e`，树 `f2a678f94b7c64623b8545ed05e33bfe2e1258ba`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `33e562c465760806cc3c93b2da697b4a65f5ecf4`，公开树 `649b41c2252dbdfb038a6fbbc0f9a4a62dc24e7b`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 41017973622 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41017973622) 的 8 个步骤均通过；匿名完整 APK、原签名、SDK 来源、源码标签与更新入口核验通过。公开验收回执 SHA-256 为 `136103bb0221cf0364cbf8f0cb1a807aa95613cee427ab4541326f6a10e97729`；发布 manifest SHA-256 为 `3d98622227dc9ee96ecb8078e00ed82b69fb81b3e1317239b0e4423d795d7302`；实际 REST 标签响应 SHA-256 为 `92c1dbeadd2af9c4eafda3db48b846614242964ae3d7ae386e7baa3b02ae8c93`。

## 尚未验证与后续

此前不合格批次及原始失败记录继续保留，不与当前源码与批次的完整成功证据混用。当前基线继承已核对的 CI 诊断导出边界，原有隐私扫描和业务验收保持不变；早前拒绝原文件的字段与类别仍未确认。真实 Gecko 进程退出、锁屏和长时间后台返回仍待手机验证。

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.40 / 93**，按既定计划退役失去页面归属的普通环境检查；独立身份检查和服务检查仍保留各自生命周期。后续版本源码或 CI 完成不代表已经发布；每版以正式 Release 与实际验证记录为准。

此前已发布说明与交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
