# GeckoView 157 能力与验证边界

产品继续使用官方 `org.mozilla.geckoview:geckoview:157.0.20261005135250`，不更换内核、不改写 ChatGPT 网页，也不在页面里伪造指纹字段。

## 已确认的作用范围

| 项目 | 官方接口与实际范围 | 当前限制 |
| --- | --- | --- |
| 移动／桌面 UA | `GeckoSessionSettings` 设置会话 UA；受控 Android 测试中，页面、同源 iframe、Dedicated Worker 与 Blob Worker 的 JS UA 跟随会话。主文档、iframe、Worker 脚本及页面 fetch 的请求头也跟随会话。 | Worker 的 fetch 请求头仍使用 SDK 移动 UA 默认值。桌面显示成功不代表所有执行环境与请求头一致。 |
| SDK 默认 UA | `GeckoSession.getDefaultUserAgent()` 提供忽略会话覆盖的 SDK 构建默认值。 | 它不是原生运行时应用确认，也不能代替服务端实际收到的请求头。没有公开的运行时 UA setter。 |
| 语言 | `GeckoRuntimeSettings.setLocales/getLocales` 管理运行时的语言请求；同一运行时内的会话共享设置。 | getter 只说明请求值。页面、iframe、Worker 和请求头必须分别观测；例如 `zh-Hant-TW` 的内容规范化需要按 SDK 实际结果核对。 |
| 时区 | 当前跟随设备；真实网页通过 `Intl` 与时区偏移读取结果。 | 未提供独立环境时区控制。 |
| 隐私保护 | 沿用官方内核提供的保护策略及现有设置应用流程。 | 不承诺独立 Canvas、WebGL、音频或字体伪装；强化保护的真实兼容性另行验收。 |
| 环境隔离 | 保留现有环境进程、目录、稳定身份、加密凭据和升级数据迁移。 | 同一运行时内的两个受控会话不能证明不同 Android 环境互相隔离；真实登录、重启和 ARM 手机仍需验收。 |

## 实测差异与诊断规则

源码 `e970c19b9f5e59144e8b718c45579eaf57a40e4a` 的 Android SDK 原型在第二个桌面／日语案例中失败：JS UA 与四类文档所属请求头为桌面 UA，另外两类 Worker fetch 请求头为移动 UA。六类请求均真实到达受控服务器，语言均为 `ja-JP,en-US;q=0.9`。这是作用范围差异，不是请求或角色缺失。

原始失败报告保留于 [不可变测试产物](https://github.com/Ararataki-number-one/yuanying-chat/blob/942920ea1a73f79b6796cf9f05f2e3fc9e67011c/gecko-identity-prototype-results.json)。这一轮的 15 份常规 Android 报告通过，环境模型 32 项与意图恢复 43 项通过；SDK 原型未通过，因此该次结果没有用于签名发布。

后续诊断仍采集每个会话的六类真实请求头：文档所属请求对照原生会话 getter，Worker fetch 对照独立 SDK 默认 getter。必须保留实际不一致、原始服务器记录、配置与 APK 来源、调用 nonce 和未覆盖范围。诊断通过表示实际行为符合记录的 SDK 范围，不表示完整桌面指纹、真实账号登录或正式发布验收通过。关闭联网保护后的真实 fetch／Worker 拒绝与服务器零新增请求验证仍须通过。

跨源 iframe、Shared Worker、Service Worker、真实 ChatGPT 登录、最新 Android 真机与公网速度不属于这个受控原型的通过范围。已知输入光标跳位也没有被这项诊断修复。

## 后续可验证的方向

官方扩展 `webRequest.onBeforeSendHeaders` 提供真实浏览器 HTTP 请求头修改通路，但当前未增加权限或实现 UA 对齐。若以后采用，必须先验证环境与配置版本归属、旧 Worker 和弹窗、不能修改的请求、后台恢复，以及 ARM 手机上的开销。不能把它当作网络断流保护，也不能用页面 JS 或服务端假回执代替真实结果。
