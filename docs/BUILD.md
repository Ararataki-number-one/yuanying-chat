# 构建 1.5.24

正式应用现已接入 Mozilla 官方 GeckoView。使用 Gradle 构建以合并 SDK 的 Java、原生库、资源、服务和依赖；旧版手工 AAPT2/D8 流程不再适用于本版本。

## 工具与构建

使用 JDK 17、Android SDK Platform 37.1、Build Tools 37.0.0。最低 Android 8，独立环境需要 Android 9。Gradle Wrapper 固定 9.8.0 并校验发行包 SHA-256；AGP 9.4.1、Mozilla 官方 GeckoView `157.0.20261005135250`（Firefox 157.0.1）固定在构建文件。[官方 SDK 来源收据](../third-party/sdk/geckoview-157.0.1-official.json) 记录 AAR、POM、源码包和准确上游 revision。

```bash
# ANDROID_HOME 指向已安装的 Android SDK，JAVA_HOME 指向 JDK 17。
./gradlew :app:assembleRelease
./gradlew :app:assembleIntegration
```

Windows 使用 `gradlew.bat`。发布输出在 `app/build/outputs/apk/release/`，包含 ARM64 和 x86_64 的未签名包。独立回归输出在 `app/build/outputs/apk/integration/`，包名 `local.pocketchat.test`，采用非调试构建和测试签名。发布包不包含回归 Activity 或 HTTP 样本入口。

当前公网 APK 是 ARM64，适合常见 Android 手机。旧测试记录对应当时的内核，不替代 Gecko 设备验证。

## 原签名覆盖安装

用户提供的原密钥保存在被 Git 忽略的 `work/android-test/private/local-test.jks`，不进入源码、CI 或发布附件。缺少原密钥时构建未签名包；签名助手会报错，不会偷偷生成替代密钥。

```bash
python3 tools/sign-apk.py app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk \
  --key work/android-test/private/local-test.jks \
  --tools "$ANDROID_HOME/build-tools/37.0.0" --java "$JAVA_HOME/bin/java"
```

输出 `dist/PocketChat-1.5.24-gecko-arm64.apk` 和签名检查记录。助手从 `app/build.gradle` 读取版本，检查原证书、包名 `local.pocketchat`、当前版本号 50、非调试构建、无测试入口及 16 KB 对齐。原版证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。不同证书的预览包不能覆盖原版。

## 云环境

已准备工具位于 `work/cloud-setup/jdk/` 与 `work/gecko-sdk-validation/`。`python3 engine-probe/tools/setup.py` 用官方地址与固定校验和准备 SDK 37.1、Build Tools 37、Gradle 和早期验证包所用的 Gecko AAR；它只写忽略目录。该独立验证包保留历史 SDK pin，正式应用 SDK 以 `app/build.gradle` 与上述来源收据为准。

本云容器的 Maven Central 返回 429，完整 Gradle 构建通过 `.github/workflows/gecko-integration.yml` 在 GitHub runner 执行。该工作流先校验官方 SDK 和 Gradle，再运行发布编译、发布版 LintVital、回调生命周期检查和 Android 15 KVM 回归。不要将本地 javac 成功描述为完整 APK 构建成功。

无需常驻服务即可进行编译。设备回归需要 Android 设备或带 KVM 的模拟器，受控样本与 HTTP/SOCKS 服务由 `tests/gecko/run_device.py` 启动并结束。真实 Google/ChatGPT 登录需要在手机上验收，不在合成样本测试范围内。

正式源码只使用官方 GeckoView；不再依赖 AndroidX WebKit，不打包旧简洁页面及其渲染库。正常验收保留原网页输入、存储、上传、下载和环境线路检查，并追加仅原网页、前台安静／后台选用以及更新线路续传检查。公开 SDK AAR 校验和固定，未使用输入实验补丁。

工作流在构建前核验官方 AAR/POM/源码包，构建后再次核验 Gradle 实际解析到的完整 AAR。`tools/gecko/verify_official_sdk.py` 只读取并比对，不重写 AAR、SDK 类或原生库。SDK 来源核验和编译通过不代表输入问题已修复；仍需保留原单次 Android 硬件输入、草稿与选择范围断言，全部正常设备验收通过后才能发布。

## 入口、出口与加密存储回归

入口和出口订阅分别保存地址、节点、更新状态和独立标识。环境保存私有的入口、出口快照；共享订阅刷新不重写正在运行的环境。候选网络在安全空闲时应用，固定出口不随机。

加密文件的恢复、读取、发布和删除必须经过 `SealedFileIo`。保持原 Keystore 别名、GCM 数据格式和 slot AAD；跨进程锁使用最多 64 个稳定文件，成功返回前校验实际发布的字节。可运行无需额外 Java 依赖的主机检查：

```bash
python3 tests/sealed-file-host/run.py --java-home "$JAVA_HOME"
```

该流程验证 32 项主机检查，不执行 Android Keystore。订阅目录、源快照和待应用设置的其他主机检查使用固定校验和的 `org.json:json:20240303`；下载、校验和运行命令见当前 Gecko 工作流。

设备验收还要求独立订阅管理的真实点击、Android 加密读写竞争、固定出口链式连接、回复期间的候选应用、原网页输入和原生缩放／键盘位置检查。受控 HTTPS 样本的 CA、NSS 数据库和服务器证书只属于 `local.pocketchat.test`；正式 APK 必须排除整个测试信任目录和所有 JKS／PKCS#12 文件。
