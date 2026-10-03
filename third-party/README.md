# 第三方组件

本目录保留第三方组件的原始许可文件及对应源码材料。

| 组件 | 版本或说明 | 许可材料 |
| --- | --- | --- |
| Mihomo | v1.19.31，未修改的 Android ARM64、x86_64 二进制 | [GPL-3.0](licenses/Mihomo-GPL-3.0.txt)、[对应上游源码](source/mihomo-v1.19.31.tar.gz) |
| AndroidX WebKit | 1.12.1 | [POM](licenses/AndroidX-WebKit.pom)、[Apache-2.0](licenses/Apache-2.0.txt) |
| AndroidX Core | Gradle 发布使用 Gecko 的传递依赖；旧手工构建保留 1.1.0 | [Apache-2.0](licenses/Apache-2.0.txt) |
| DOMPurify | 保留本仓库捆绑的版本 | [原始许可](licenses/DOMPurify.txt) |
| Marked | 保留本仓库捆绑的版本 | [原始许可](licenses/Marked.txt) |
| KaTeX | 保留本仓库捆绑的版本 | [原始许可](licenses/KaTeX.txt) |

Mihomo 上游：[MetaCubeX/mihomo v1.19.31](https://github.com/MetaCubeX/mihomo/tree/v1.19.31)。二进制位于 `app/src/main/jniLibs/`，GPL 文本同时保留在 APK 资源中。其他组件的捆绑文件与原有说明也保留在 `libs/` 和 `app/src/main/assets/vendor/`。

## Mozilla GeckoView

正式包使用未经修改的官方预编译 `org.mozilla.geckoview:geckoview:157.0.20260924084938`。AAR SHA-256：`25de06a6204382c08e405adc36da7373098bdc230d6d768f17a6fe971f0dece0`。

- [官方 Maven SDK](https://maven.mozilla.org/maven2/org/mozilla/geckoview/geckoview/157.0.20260924084938/)
- [该发行包 POM 所指的准确上游源码](https://hg.mozilla.org/releases/mozilla-release/rev/8eb25af4acf031ab1e06abf1a912275083c820ed)
- [对应源码目录](https://hg.mozilla.org/releases/mozilla-release/file/8eb25af4acf031ab1e06abf1a912275083c820ed/)
- [Mozilla 原始许可汇总，包含 MPL 2.0](licenses/Mozilla-Gecko-License.html)（汇总文本来自官方 gecko-dev 镜像；准确发行源码以上述 revision 为准）

SDK 的原生库、内部网页和许可材料保留原样。应用仅加入独立的 Java 适配层和内置路由扩展，没有改动 Mozilla 引擎源文件。AndroidX 的传递依赖使用各自 Apache 2.0 许可。Mozilla、Firefox 的商标不属于本项目。
