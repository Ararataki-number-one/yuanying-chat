# 2.0.26：环境身份与配置状态

versionCode 79，扩展版本 2.0.26.79。正式版已发布，原证书可覆盖升级：[下载 ARM64 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v2.0.26-gecko/PocketChat-2.0.26-gecko-arm64.apk)。本次只更新 2.0.26，后续版本按顺序单独推进。

- 在环境模板与自检中增加当前环境身份总览，集中显示模板、语言、保护等级、线路归属和配置版本。
- 区分“已保存、等待应用、已确认、观测存在差异”；旧环境、旧配置或过期页面的结果不能确认当前网页。
- 修正线路核验撤销后短暂显示“已获准”的边界：总览复用原有权威准入判断，并继续检查原生保护状态。

保持单 GeckoView 与 ChatGPT 原网页，沿用已有配置、保护、登录与文件流程。本版没有加入 2.0.27—2.0.30 的后续功能。

## 本版验证

源码 `766a4b1ee206cc2ddca059f5c2682693f45de7bf`。正式受控运行 [40647812827/1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40647812827) 的 11 个任务全部通过，十项原发布门禁各执行一次，没有重跑或混用其他版本结果。完整 Release/Integration 编译、SDK 来源核验及 531 项主机回归通过。

主输入与两个独立输入样本的性能检查分别为 163／163／164 项，光标检查各 129 项、14 个场景，使用同一编译 APK 与 SDK。身份状态模型在桌面与 Android JSON 两种实现上检查；界面适配器的 3 项准入对照在两种 JSON 上通过。适配器主机检查使用真实 Android framework JAR 与声明过的应用／Gecko doubles，不能等同于 Android UI 执行。

真实手机、ChatGPT 官网、百度输入法界面与实际保护效果仍未验收；没有据此宣称手机提速或真实线路延迟改善。

## 正式发布与独立核验

合格未签名产物为 `4236e779c3f6e2c45f17f59022311989ae3f6e22`，源码与应用版本不含后续四版功能。沿用固定派生 Gecko SDK、原签名和十项原发布门禁；没有以发布授权代替真机验收。

[发布运行 40660638153/1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/40660638153) 全步骤成功。随后独立匿名下载整个公开 APK，并核对包名、79版本号、ARM64、原证书、SDK 来源、16KB 对齐、测试组件排除和更新入口。标签通过 GitHub API 另行核对，精确指向上述源码。

- APK：`PocketChat-2.0.26-gecko-arm64.apk`，119320229 字节。
- SHA256：`1f9787ef6f91e8c97c03f7aca339ec7fb05f498627feb785b8a73214006552a7`。
- 原证书 SHA256：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。
- 更新通道提交：`a91a88ee6978cb52e871dbef82331b302770c584`。

受控 Android 与公开产物核验不代表真实手机、百度输入法或官网保护效果已通过。后续版本继续逐版开发、验证和发布。
