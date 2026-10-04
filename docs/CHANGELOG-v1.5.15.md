# 1.5.15 图片选择与手动测速修复

## 修改与原因

Java 文件位于 `app/src/main/java/local/pocketchat/`。

| 文件 | 修改 |
| --- | --- |
| `Attachments.java` | 原网页主动请求文件选择时，不再因应用的等待回复状态直接拒绝。遵循网页的 MIME / 扩展名列表与多选要求打开系统文件选择器。原网页结果直接交回浏览器，不创建基于文件名的原生上传状态；保留当前页面、导航代号、URI 与取消校验。简洁模式保留既有附件管理。 |
| `GeckoUploadFiles.java` | 复制系统文档到当前环境的临时文件时，对无匹配扩展名的图片按提供方 MIME 补充后缀，使 Firefox 文件对象保留图片类型。现有流式复制、空间上限与清理保持。 |
| `NetworkUiProvider.java` | 手动完整线路测速在通用忙碌拦截前处理，避免当前回复或附件状态阻止用户测速。配置切换、重连和出口核验保留原保护。 |
| `NetworkWork.java`、`NativeNetwork.java`、`ChatSession.java` | 区分显式手动测速与后台维护。手动仅探测当前线路，忙碌时不自动取消；自动维护仍暂停。任务交接和暂停判断在同一锁内执行，避免空引用或误取消新任务。新提交、连接变化仍可取消检测，不切换入口或重载网页。 |
| `app/build.gradle`、`app/src/main/AndroidManifest.xml` | 统一正式版本 1.5.15 / code 41。 |
| `tests/gecko/GeckoIntegrationTestActivity.java`、`GeckoUploadFixtureProvider.java`、`AndroidManifest.xml`、`run_device.py` | 增加真实 Gecko 电脑版文件输入，调用生产 `Attachments.chrome()` 与结果处理，等待状态保持，检查 MIME / 多选 Intent；用无扩展名流式 PNG 验证文件类型、4×3 解码和 HTTP multipart 实际接收，不产生虚假原生上传状态。只有受控页面来源适配和选择结果注入属于测试适配。 |
| `tests/gecko/NetworkOptimizationIntegrationActivity.java` | 真实 Android / Mihomo 回复忙碌状态手动测速成功，核验入口、固定出口与连接代号保持；既有忙碌后台维护停止用例保留。 |
| `tools/publish-gecko-release.py` | 1.5.15 起发布要求新增电脑版图片回归通过，防止只测文本回调就发布。 |

## 验证边界

新增图片回归使用真实浏览器、生产选择逻辑和 HTTP 上传；系统 DocumentsUI 的手动选图步骤由受控结果注入替代。未使用真实 ChatGPT 账号，因此不把受控验证描述为真实网站上传验收。正式包不包含受控页面、测试提供方或测试适配。

完整构建、受控 Android 上传和网络回归、公网原签名 APK 与自动更新源验证见 [验证报告](../verification/upload-speed-v1.5.15/README.md)。
