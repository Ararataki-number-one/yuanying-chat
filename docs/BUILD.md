# 构建 2.1.0 双内核版本

ChatGPT 增强界面以 Mozilla 官方 GeckoView 为基础，使用固定来源、源码派生的输入同步修正 SDK；通用浏览器使用系统 Chromium 和 AndroidX WebKit 1.14.0。使用 Gradle 构建以合并 SDK 的 Java、原生库、资源、服务和依赖；旧版手工 AAPT2/D8 流程不再适用于本版本。

## 工具与构建

使用 JDK 17、Android SDK Platform 37.1、Build Tools 37.0.0。minSdk 26（Android 8）、targetSdk 35；渲染进程的部分隔离选项按系统 API 条件启用。Gradle Wrapper 固定 9.8.0 并校验发行包 SHA-256；AGP 9.4.1、Mozilla 官方 GeckoView `157.0.20261005135250`（Firefox 157.0.1）固定在构建文件。[官方 SDK 来源收据](../third-party/sdk/geckoview-157.0.1-official.json) 记录 AAR、POM、源码包和准确上游 revision。

首次构建须先按 [Gecko CI](../.github/workflows/gecko-integration.yml) 下载并核验固定的官方 AAR、POM、源码和依赖，再执行 `tools/gecko/caret_workflow.py prepare` 生成本次派生 SDK、来源回执及本地 Maven 目录。下列 Gradle 命令以这些输入已经准备好为前提；不能直接省略此步骤或把旧目录当作当前源码的通过记录。集成包另需运行 `python3 tools/gecko/generate_appearance_fixture.py` 准备仅测试使用的原生桥接样本；release 不使用该覆盖资源。

```bash
# ANDROID_HOME 指向已安装的 Android SDK，JAVA_HOME 指向 JDK 17。
./gradlew :app:assembleRelease
./gradlew :app:assembleIntegration
```

Windows 使用 `gradlew.bat`。发布输出在 `app/build/outputs/apk/release/`，包含 ARM64 和 x86_64 的未签名包。独立回归输出在 `app/build/outputs/apk/integration/`，包名 `local.pocketchat.test`，采用非调试构建和测试签名。发布包不包含回归 Activity 或 HTTP 样本入口。

当前公网 APK 是 ARM64，适合常见 Android 手机。旧测试记录对应当时的内核，不替代 Gecko 设备验证。

## 原签名覆盖安装

原签名密钥须由维护者提供，保存在 Git 忽略目录，不进入源码、CI 或发布附件。文件名与存放路径不能证明签名身份，必须核对证书指纹。缺少原密钥或证书不匹配时保留未签名包；签名助手会报错，不会生成替代密钥。以下路径是维护者准备原密钥后的示例，不表示工作区已经具备原签名。

```bash
python3 tools/sign-apk.py app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk \
  --key work/release-signing/original-release.jks \
  --tools "$ANDROID_HOME/build-tools/37.0.0" --java "$JAVA_HOME/bin/java"
```

输出 `dist/PocketChat-<version>-gecko-arm64.apk` 和签名检查记录。助手从 `app/build.gradle` 读取本次版本及 versionCode，检查原证书、包名 `local.pocketchat`、非调试构建、无测试入口及 16 KB 对齐。原版证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。不同证书的预览包不能覆盖原版。

## 云环境

已准备工具位于 `work/cloud-setup/jdk/` 与 `work/gecko-sdk-validation/`。`python3 engine-probe/tools/setup.py` 用官方地址与固定校验和准备 SDK 37.1、Build Tools 37、Gradle 和早期验证包所用的 Gecko AAR；它只写忽略目录。该独立验证包保留历史 SDK pin，正式应用 SDK 以 `app/build.gradle` 与上述来源收据为准。

2.1.0 的完整构建与验收通过 `.github/workflows/browser-2_1-acceptance.yml` 在 GitHub runner 执行，分支为 `release/browser-2.1.0`。本地网络错误以本次实际请求为准。该工作流保留原有 Gecko 验收门槛，增加必需的 `lintRelease`、29 组主机检查，以及使用同批 APK 的真实 Android WebView 验收。主机 API 编译不能代替完整 APK 构建。构建产物仍未使用正式版原签名。

无需常驻服务即可进行编译。设备回归需要 Android 设备或带 KVM 的模拟器，受控样本与 HTTP/SOCKS 服务由 `tests/gecko/run_device.py` 启动并结束。真实 Google/ChatGPT 登录需要在手机上验收，不在合成样本测试范围内。

Gecko 增强界面保留原网页输入、存储、上传、下载、环境线路、前台安静／后台选用及更新续传检查。Chromium 通用浏览器不注入 ChatGPT 专用桥接，另行验证导航、标签、文件选择、下载、线路失效和界面往返；它不继承 Gecko 的指纹模板或 WebRTC 限制。应用不打包旧简洁页面及其渲染库。官方输入 AAR 校验和固定；Gecko 运行包使用 `third-party/gecko/` 与 `tools/gecko/build_caret_sdk.py` 声明的源码派生输入同步修正。当前证据以本次 SDK 来源回执、Gradle 实际解析结果和同源码验收为准，历史候选 JSON 不等于当前 Android 验收。

工作流在构建前核验官方 AAR/POM/源码包，再按固定源码和配方生成派生 AAR，构建后核验 Gradle 实际解析的派生 AAR、源回执及保持不变的 SDK 载荷。`tools/gecko/verify_official_sdk.py` 只读取并比对，不重写 AAR、SDK 类或原生库。SDK 来源核验和编译通过不代表输入问题已修复；仍需保留原单次 Android 硬件输入、草稿与选择范围断言，全部正常设备验收通过后才能发布。

## 入口、出口与加密存储回归

入口和出口订阅分别保存地址、节点、更新状态和独立标识。环境保存私有的入口、出口快照；共享订阅刷新不重写正在运行的环境。候选网络在安全空闲时应用，固定出口不随机。

加密文件的恢复、读取、发布和删除必须经过 `SealedFileIo`。保持原 Keystore 别名、GCM 数据格式和 slot AAD；跨进程锁使用最多 64 个稳定文件，成功返回前校验实际发布的字节。可运行无需额外 Java 依赖的主机检查：

```bash
python3 tests/sealed-file-host/run.py --java-home "$JAVA_HOME"
```

主机用例及计数以当前源码和本次运行报告为准；主机流程不执行 Android Keystore。订阅目录、源快照和待应用设置的其他主机检查使用固定校验和的 `org.json:json:20240303`；下载、校验和运行命令见当前 Gecko 工作流。

设备验收还要求独立订阅管理的真实点击、Android 加密读写竞争、固定出口链式连接、回复期间的候选应用、原网页输入和原生缩放／键盘位置检查。受控 HTTPS 样本的 CA、NSS 数据库和服务器证书只属于 `local.pocketchat.test`；正式 APK 必须排除整个测试信任目录和所有 JKS／PKCS#12 文件。
