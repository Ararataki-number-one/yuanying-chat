# 第三方组件

本目录保留第三方组件的原始许可文件及对应源码材料。

| 组件 | 版本或说明 | 许可材料 |
| --- | --- | --- |
| Mihomo | v1.19.31-pocket-reading1，基于 v1.19.31 和仓库中的探测及固定出口补丁，Android ARM64、x86_64 | [GPL-3.0](licenses/Mihomo-GPL-3.0.txt)、[原始上游源码](source/mihomo-v1.19.31.tar.gz)、[修改补丁](patches/mihomo-v1.19.31-probe.patch)、[构建与行为说明](patches/mihomo-v1.19.31-probe.md) |
| AndroidX WebKit | 1.14.0，2.1.0 用于系统 Chromium 的受控代理；历史 1.12.1 材料继续保留 | [1.14.0 POM](licenses/AndroidX-WebKit-1.14.0.pom)、[历史 POM](licenses/AndroidX-WebKit.pom)、[Apache-2.0](licenses/Apache-2.0.txt) |
| AndroidX Core | Gradle 发布使用 Gecko 的传递依赖；旧手工构建保留 1.1.0 | [Apache-2.0](licenses/Apache-2.0.txt) |
| SnakeYAML | 2.3，网络分享从缓存订阅中提取选定节点，使用受限 SafeConstructor | [Apache-2.0](licenses/Apache-2.0.txt)、[对应 Maven 源码与 POM](https://repo.maven.apache.org/maven2/org/yaml/snakeyaml/2.3/) |
| DOMPurify | 仅保留历史许可，1.5.20 不再打包 | [原始许可](licenses/DOMPurify.txt) |
| Marked | 仅保留历史许可，1.5.20 不再打包 | [原始许可](licenses/Marked.txt) |
| KaTeX | 仅保留历史许可，1.5.20 不再打包 | [原始许可](licenses/KaTeX.txt) |

Mihomo 上游：[MetaCubeX/mihomo v1.19.31](https://github.com/MetaCubeX/mihomo/tree/v1.19.31)。二进制位于 `app/src/main/jniLibs/`，GPL 文本同时保留在 APK 资源中。历史组件的原始许可继续保留；1.5.20 删除旧简洁页面及 `app/src/main/assets/vendor/`，正式 APK 不再包含这些渲染库。

Mihomo 从 1.5.20 起使用本项目的探测补丁，不再将二进制描述为“未经修改”。原始源码归档保留原样；补丁修复测速取消、重新拨号和第二次请求失败后的耗时计算，不改变网页流量转发或 TLS 验证。两个 Android ABI 使用 Go 1.26.8、NDK 29.0.13113456、API 26、CGO 和 16 KiB 页对齐构建。[构建 receipt](patches/mihomo-v1.19.31-probe-build.json) 记录输入、参数和二进制 SHA-256；[构建脚本](../tools/build-mihomo.py) 提供重建与只读核验。构建核验不能替代实际 Android 验收。

## Mozilla GeckoView

上游构建输入为 Mozilla 官方的 `org.mozilla.geckoview:geckoview:157.0.20261005135250`（Firefox 157.0.1）。正式应用使用派生 SDK `local.pocketchat.sdk:geckoview-caret:157.0.20261005135250-pocket3`。构建脚本从修正后的 Java 源码编译并替换 `GeckoEditable.class`，其余类、原生库和资源保持上游内容。[官方输入收据](sdk/geckoview-157.0.1-official.json) · [派生构件收据](sdk/geckoview-157.0.1-editable-selection.json) · [输入修正及补丁说明](gecko/README.md)

- [官方 Maven SDK](https://maven.mozilla.org/maven2/org/mozilla/geckoview/geckoview/157.0.20261005135250/)
- [该发行包 POM 所指的准确上游源码](https://hg.mozilla.org/releases/mozilla-release/rev/737ec77d798755890b062aab541a90d6c75afd19)
- [对应源码目录](https://hg.mozilla.org/releases/mozilla-release/file/737ec77d798755890b062aab541a90d6c75afd19/)
- [Mozilla 原始许可汇总，包含 MPL 2.0](licenses/Mozilla-Gecko-License.html)（汇总文本来自官方 gecko-dev 镜像；准确发行源码以上述 revision 为准）

修改后的 `GeckoEditable.java` 保留了上游 MPL 2.0 声明。AndroidX 的传递依赖使用各自 Apache 2.0 许可。Mozilla、Firefox 的商标不属于本项目。

## Cefrium Chromium

选装 Chromium 组件使用 Cefrium 0.21.0 Libre，内核为 Chromium 156.0.8078.96。基础安装包提供 GeckoView。Cefrium 许可为 [LGPL-3.0-or-later](../chromium/src/main/assets/licenses/Cefrium-LGPL-3.0.txt)，配套 [GPL-3.0 文本](licenses/Mihomo-GPL-3.0.txt) 同时包含在基础安装包中。CEF 的原始代码采用 BSD 三条款许可。Cefrium Android 移植版权属于 Juan Manuel Mendez Rey，原 CEF 版权属于 Marshall A. Greenblatt 及贡献者。

- [对应上游源码 v0.21.0](https://codeberg.org/cefrium/cef-android/archive/v0.21.0.tar.gz)
- [上游构建说明](https://codeberg.org/cefrium/cef-android/src/tag/v0.21.0/BUILD-GUIDE-CEFRIUM.md)
- [完整第三方声明](https://codeberg.org/cefrium/cef-android/releases/download/v0.21.0/cefrium-sdk-0.21.0-NOTICE.txt)，同一文件也包含在 Chromium 选装组件中

下游 Gradle 配置和 Android 资源打包规则包含在本版本源码中。自行编译时，先按上游说明构建替换件，再更新本地 Maven 仓库和对应的构件摘要，使用 `-PpocketChatChromiumBundle=true` 构建基础包和选装组件。两份 APK 可以使用同一个自有签名密钥签名，并安装到单独的测试设备或用户环境验证。
