# 1.5.13 Oil UI 校准与原生视觉验证

源码：`e56fc8715ded0473cd0e97224136d4ef95070bce`。正式包：`local.pocketchat`，1.5.13 / code 39。

沿用 AdsPower 管理方向和既有 HTML 参考，应用 [Oil UI 开源版 0.15.3](https://github.com/oil-oil/oil-ui/blob/81e194cefa51be3f3f41083aa3a8e28b1331cd23/SKILL.md) 的已有界面润色流程。见 [设计说明](../../docs/ui/OIL-UI-DIRECTION.md) 与 [逐文件修改](../../docs/CHANGELOG-v1.5.13.md)。

## 实际原生画面

Android 15 / API 35 实例取得 30 张原生截图和对应控件树。每种样式覆盖 360 × 640 dp、412 × 640 dp 的会话外壳、环境列表、网络列表、代理编辑、入口选择、浏览器设置；另覆盖 360 × 640 dp / 系统字体 200% 的代理编辑、入口选择、浏览器设置。

对照样式来自 `45b4d44528ad54fc7d54299fa9f6091a90446f79`。仅恢复八个视觉源文件，两份测试 APK 的核心源码、版本号、本地合成数据和测试签名一致。这是样式对照，不是把旧正式 APK 冒充同一实现。正式 ARM64 发布包在当前源码下单独编译；对照构建没有替换正式包。

| 画面 | 对照 | 当前 |
| --- | --- | --- |
| 会话外壳 / 360 dp | [之前](ui-visuals/baseline-360x640-font1-chat.png) | [现在](ui-visuals/current-360x640-font1-chat.png) |
| 环境列表 / 360 dp | [之前](ui-visuals/baseline-360x640-font1-environments.png) | [现在](ui-visuals/current-360x640-font1-environments.png) |
| 网络列表 / 360 dp | [之前](ui-visuals/baseline-360x640-font1-network.png) | [现在](ui-visuals/current-360x640-font1-network.png) |
| 代理编辑 / 360 dp | [之前](ui-visuals/baseline-360x640-font1-proxy.png) | [现在](ui-visuals/current-360x640-font1-proxy.png) |
| 入口选择 / 412 dp | [之前](ui-visuals/baseline-412x640-font1-entries.png) | [现在](ui-visuals/current-412x640-font1-entries.png) |
| 浏览器设置 / 360 dp | [之前](ui-visuals/baseline-360x640-font1-browser.png) | [现在](ui-visuals/current-360x640-font1-browser.png) |
| 代理编辑 / 大字体 | [之前](ui-visuals/baseline-360x640-font2-proxy.png) | [现在](ui-visuals/current-360x640-font2-proxy.png) |
| 入口选择 / 大字体 | [之前](ui-visuals/baseline-360x640-font2-entries.png) | [现在](ui-visuals/current-360x640-font2-entries.png) |
| 浏览器设置 / 大字体 | [之前](ui-visuals/baseline-360x640-font2-browser.png) | [现在](ui-visuals/current-360x640-font2-browser.png) |

[独立评审与处理记录](VISUAL-REVIEW.md)。本轮按已有规范评审，不打分；静态截图不证明动效、完整键盘流程或真实账号登录。会话画面使用实际未配置网络的状态，只验收原生外壳，不用本地网页冒充官方聊天页面。合成网络记录保留未连接状态，没有伪造出口核验或连接成功。

## 构建与回归

[Release / integration 编译、Lint Vital 与 Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37192734643)通过。105 项主机检查通过：18 项请求生命周期、39 项阅读、10 项 Cookie、23 项更新、15 项地区解析。Android 实际执行 77 次受控操作，继续覆盖环境隔离、HTTP/SOCKS 线路、附件与下载、页面关闭恢复、缩放、回复期间保存配置、后台应用、删除与自动更新。

## 正式包与公网

原签名 APK：`PocketChat-1.5.13-gecko-arm64.apk`，120450289 字节，SHA-256：`bd8f35d83e4a2a7cfeb670881f0dd59923599356c40d4e32526f7f63ef587a68`。证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。非调试、无测试组件、16 KB ZIP 对齐。公网匿名完整下载通过；自动更新源版本、字节数、哈希与公开 APK 一致。

[下载 1.5.13 正式 APK（ARM64）](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.13-gecko/PocketChat-1.5.13-gecko-arm64.apk)，可以覆盖原签名版本。

## 验证边界

仅调整原生 UI，没有替换官方网页、浏览器内核、登录目录或网络连接实现。测试使用独立包与合成数据，没有真实 Google / ChatGPT 账号或 ARM 手机；真实账号长期登录、真实生成文件链接、偶发白屏和厂商后台策略沿用前版的真机验收边界。本轮没有动效改动，也没有声称完成动效评审。
