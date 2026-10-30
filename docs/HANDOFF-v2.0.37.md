# 2.0.37 公开开发交接

当前正式版为 **2.0.37 / versionCode 90**。标签 [v2.0.37-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.37-gecko) 对应源码 `c6f8b5456407a30461fb96c55b6657410d9aad07`，源码树为 `f28ec024efd18c750c6f4db6a52181b496ec62db`。详见 [发布说明](RELEASE-v2.0.37.md)；原签名正式包可覆盖升级。

本版在文件提供者调用返回后检查取消状态，停止后续数据块或文件准备，提前清理尚未交给网页的附件副本并保留清理失败记录；已交付或归属未知的副本继续保留。存储详情通过已有工作线程进行有界只读采样，显示前复核环境与界面归属。阻塞中的提供者或文件系统调用仍须先返回，才能继续取消；采样容量不表示可安全删除容量。继续保留单 GeckoView、ChatGPT 原网页、独立环境、固定出口、登录与草稿，不自动回收已交付附件。

## 已核验的发布证据

- [主验收 41002427736 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41002427736)、[Profile 41002427592 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41002427592)、[Mihomo 41002427600 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41002427600)：共 14 个实际任务通过；原有 10 项 CI 校验与本地重放均通过，9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本及 111 项界面截图通过。不同批次的证据不混用。
- 正式 ARM64 APK 为 `PocketChat-2.0.37-gecko-arm64.apk`，119352997 字节，SHA-256 为 `a3b518ac344d5a64de6dd712fed2c3063156feb881a39f2770fe9da74590e903`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `defe306a9a65b7d7dad021c6a65194d29b932787`，树 `9d5719a519dd461a5ab8c5ec6a7d5b013572cb93`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `096ff8f456fddf2f8c17213fb8841addc1d8e101`，公开树 `b51d8ffd5874c36e23935c347c2104902dd64d6f`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 41006840568 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/41006840568) 的 8 个步骤均通过；匿名完整 APK、原签名、SDK 来源、源码标签与更新入口核验通过。公开验收回执 SHA-256 为 `7b855ad29ced6d6ff575f3fd55b070594abff788780c58eb44cf3f4e3126c661`；发布 manifest SHA-256 为 `5ca020347bbf373a31daf9fb20e5f99494555517ad2c85b5c3db202550b17b13`；实际 REST 标签响应 SHA-256 为 `25bb404935a6d8ed9992cf2de51ad557545b5ecad3540d31b56d9684a744c1c7`。

## 尚未验证与后续

此前版本不合格批次及原始失败记录继续保留，不与当前源码与批次的完整成功证据混用。真实手机上的文件选择器、阻塞提供者取消响应与存储界面仍待验收。

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.38 / 91**，按既定计划减少下载历史的重复查询与列表更新，现阶段不声称已经分页或虚拟化。后续版本源码或 CI 完成不代表已经发布；每版以正式 Release 与实际验证记录为准。

此前已发布说明与交接继续原样保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
