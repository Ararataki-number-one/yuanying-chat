# 2.0.33 公开开发交接

当前正式版为 **2.0.33 / versionCode 86**。标签 [v2.0.33-gecko](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.33-gecko) 对应源码 `70e866feb250d2637e7df18d27a2709680bca91f`，源码树为 `ad09412aedd7a64a1a0e6e1563c24e6ab95b2831`。详见 [发布说明](RELEASE-v2.0.33.md)；原签名正式包可覆盖升级。

本版将原生下载绑定到发起环境、配置代次和受保护线路。下载期间发现归属或线路核验变化时暂停、保留部分文件，恢复时重新核验；不增加直连兜底，不自动重发聊天。继续保留单 GeckoView、ChatGPT 原网页、独立环境、登录数据和固定出口。

## 已核验的发布证据

- [主验收 40962740997 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40962740997)、[Profile 40962741235 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40962741235)、[Mihomo 40962741300 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40962741300)：共 14 个实际任务通过。主验收的原有 10 项校验与本地重放均通过；附加的 9 个独立 Android VM 检查、3 份相同安装包与 SDK 的输入样本、111 项当前界面截图均为受控验证。
- 正式 ARM64 APK 为 `PocketChat-2.0.33-gecko-arm64.apk`，119344805 字节，SHA-256 为 `4abe315236920d25508fc34d54ea20ce71baf91ace14effb232cfd78e64be0c6`。原签名证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`；正式包名为 `local.pocketchat`，不包含集成测试 Activity。
- 发布工具提交 `091ddaa8bd9257dcb434ed965eb7062244690599`，树 `cee42c68fd30c493945dc1768ad8d68a792c8994`；只增加本地恢复不可变验收输入的工作流步骤，原有校验保持不变。
- 签名产物提交 `dc4c162de881af5fec02c3550a03d1b6a2fe478a`，公开树 `6e0644cfae6749737d36150ba359a2eae1948679`；公开树只含 13 项必要发布文件，不含运行时索引或原始诊断报告。
- [发布任务 40970845420 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40970845420) 的 8 个步骤均通过。首次观察到该发布任务时已结束，此记录不声称在结论产生前观察到它。
- 匿名完整 APK、原签名、SDK 来源、源码标签和更新入口均核验通过。公开验收回执 SHA-256 为 `5e8dd12d9cd24155125ccadf2325bddc84d53c147e044eb996eeb1e3830156e6`；发布 manifest SHA-256 为 `192a87bc360a613751de47feca1adeb1d91a5d9944ba43cae478f9b62c9e687f`；实际 REST 标签响应 SHA-256 为 `b971d34ce0d3ebb69c79d0c167c9e62253ffbb2612eadc96f65b558b0f39c1c9`。

## 尚未验证与后续

以上受控 Android／Gecko 验收不能替代真实手机、百度输入法、官网登录与附件体验、真实 VPN 断开／切网或公网线路测速。没有确认实际手机已消除全部卡顿，也没有确认完整线路达到 200 ms；电脑版与 Worker 的完整 HTTP 身份一致性和真实抗指纹效果仍需独立验收。

下一版为 **2.0.34 / 87**，源码候选 `6cd3418f63cf3cb9c65bad102c2eafa525d693be` 的新一轮主验收为 [40968902182 / 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40968902182)，当前仍是候选，尚未发布。2.0.35、2.0.36 及后续计划同样不能按准备进度视为发布完成；下载以最新正式 Release 为准。

2.0.32 的已发布说明和交接继续保留。签名密钥、订阅令牌、代理凭据和环境私密数据不在本公开交接中。
