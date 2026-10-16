# 第三方组件

本目录保留第三方组件的原始许可文件及对应源码材料。

| 组件 | 版本或说明 | 许可材料 |
| --- | --- | --- |
| Mihomo | v1.19.31-pocket-preconnect1，基于 v1.19.31 的探测与固定出口预认证补丁，Android ARM64、x86_64 | [GPL-3.0](licenses/Mihomo-GPL-3.0.txt)、[原始上游源码](source/mihomo-v1.19.31.tar.gz)、[修改补丁](patches/mihomo-v1.19.31-probe.patch)、[构建与行为说明](patches/mihomo-v1.19.31-probe.md) |
| AndroidX WebKit（历史） | 1.12.1，1.5.20 已移除正式依赖 | [POM](licenses/AndroidX-WebKit.pom)、[Apache-2.0](licenses/Apache-2.0.txt) |
| AndroidX Core | Gradle 发布使用 Gecko 的传递依赖；旧手工构建保留 1.1.0 | [Apache-2.0](licenses/Apache-2.0.txt) |
| SnakeYAML | 2.3，网络分享从缓存订阅中提取选定节点，使用受限 SafeConstructor | [Apache-2.0](licenses/Apache-2.0.txt)、[对应 Maven 源码与 POM](https://repo.maven.apache.org/maven2/org/yaml/snakeyaml/2.3/) |
| DOMPurify | 仅保留历史许可，1.5.20 不再打包 | [原始许可](licenses/DOMPurify.txt) |
| Marked | 仅保留历史许可，1.5.20 不再打包 | [原始许可](licenses/Marked.txt) |
| KaTeX | 仅保留历史许可，1.5.20 不再打包 | [原始许可](licenses/KaTeX.txt) |

Mihomo 上游：[MetaCubeX/mihomo v1.19.31](https://github.com/MetaCubeX/mihomo/tree/v1.19.31)。二进制位于 `app/src/main/jniLibs/`，GPL 文本同时保留在 APK 资源中。历史组件的原始许可继续保留；1.5.20 删除旧简洁页面及 `app/src/main/assets/vendor/`，正式 APK 不再包含这些渲染库。

Mihomo 从 1.5.20 起使用本项目的探测补丁，不再将二进制描述为“未经修改”。原始源码归档保留原样；补丁修复测速取消、重新拨号和第二次请求失败后的耗时计算，不改变网页流量转发或 TLS 验证。两个 Android ABI 使用 Go 1.26.8、NDK 29.0.13113456、API 26、CGO 和 16 KiB 页对齐构建。[构建 receipt](patches/mihomo-v1.19.31-probe-build.json) 记录输入、参数和二进制 SHA-256；[构建脚本](../tools/build-mihomo.py) 提供重建与只读核验。构建核验不能替代实际 Android 验收。

## Mozilla GeckoView

正式构建使用未经修改的官方预编译 `org.mozilla.geckoview:geckoview:157.0.20261005135250`（Firefox 157.0.1）。AAR SHA-256：`15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268`。[固定 SDK 来源收据](sdk/geckoview-157.0.1-official.json) 包含原始 AAR、POM、源码包和内部类哈希；来源核验不替代真实 Android 输入与环境隔离验收。

- [官方 Maven SDK](https://maven.mozilla.org/maven2/org/mozilla/geckoview/geckoview/157.0.20261005135250/)
- [该发行包 POM 所指的准确上游源码](https://hg.mozilla.org/releases/mozilla-release/rev/737ec77d798755890b062aab541a90d6c75afd19)
- [对应源码目录](https://hg.mozilla.org/releases/mozilla-release/file/737ec77d798755890b062aab541a90d6c75afd19/)
- [Mozilla 原始许可汇总，包含 MPL 2.0](licenses/Mozilla-Gecko-License.html)（汇总文本来自官方 gecko-dev 镜像；准确发行源码以上述 revision 为准）

SDK 的原生库、内部网页和许可材料保留原样。应用仅加入独立的 Java 适配层和内置路由扩展，没有改动 Mozilla 引擎源文件。AndroidX 的传递依赖使用各自 Apache 2.0 许可。Mozilla、Firefox 的商标不属于本项目。
