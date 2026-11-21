# 构建 PocketChat

正式版随主包提供 GeckoView。独立 Chromium 使用 Cefrium 0.21.0，发布时作为可选分包。Gradle 负责合并 Java、原生库、资源、服务与依赖。

## 本地编译

使用 Android SDK Platform 37.1、Build Tools 37.0.0 和 JDK 25。Gecko 派生 SDK 的源码编译需 JDK 17。应用的 minSdk 为 26、targetSdk 为 35。Gradle Wrapper 固定 9.8.0，AGP 固定 9.4.1。[官方 GeckoView 来源收据](../third-party/sdk/geckoview-157.0.1-official.json) 记录固定的 AAR、POM、源码包和上游版本。

从同一 SDK 配方的已核验构建产物取得 `maven/` 和 `assets/`。如果已放在 `work/native-caret-sdk/`，Gradle 会使用默认路径。也可以指定绝对路径：

```bash
# ANDROID_HOME 指向 Android SDK，JAVA_HOME 指向 JDK 25。
# POCKETCHAT_GECKO_SDK 指向包含 maven/ 和 assets/ 的已准备目录。
./gradlew :app:assembleRelease \
  -PcaretSdkRepository="${POCKETCHAT_GECKO_SDK}/maven" \
  -PcaretSdkAssets="${POCKETCHAT_GECKO_SDK}/assets"
```

构建 Chromium 分包前，先运行 `python3 gradle/prepare-cefrium-sdk.py` 核对并准备固定依赖，再带上相同的 Gecko 路径参数运行 `:app:bundleRelease -PpocketChatChromiumBundle=true -PpocketChatChromiumAbi=arm64-v8a`。普通 APK 在 `app/build/outputs/apk/release/`，分包使用的 AAB 在 `app/build/outputs/bundle/release/`。Windows 使用 `gradlew.bat`。

## 并行安装测试包

显式指定 `-PpocketChatParallelInstall=true -PpocketChatChromiumBundle=true` 构建独立包 `local.pocketchat.parallel`。按设备 ABI 从同一 AAB 提取 `base-master.apk` 和 `chromium-master.apk`，使用同一证书签署，再通过 `adb install-multiple base-master.apk chromium-master.apk` 一次提交。安装后从环境设置选择 Chromium。并行版使用独立的环境、登录资料和默认下载目录，环境配置备份仅传递可移植设置。

设备验证使用一次性测试密钥。将来若发布并行版，由维护者在受控工位建立专用签名密钥，将加密密钥库及恢复副本分开保存，口令由独立的私有凭据库保管。在首次正式使用前实测恢复，记录公开证书的 SHA-256 指纹。主包和分包都由该证书签署，并行版后续更新沿用同一证书。

## 正式验收的 SDK 准备

[完整发布验收](../.github/workflows/browser-2_1-acceptance.yml) 先下载并核对官方 AAR、POM、源码和固定工具链。以下调用在该工作流内使用，工作目录包含 `geckoview.aar`、`geckoview.pom`、`geckoview-sources.jar` 和 `gradle/gradle-9.8.0/`。`ANDROID_HOME` 指向 Android SDK，`JAVA_HOME` 指向 JDK 17，运行批次由 GitHub Actions 提供。

```bash
python3 tools/gecko/caret_workflow.py prepare --work work/gecko-integration
```

该步骤生成派生 SDK、来源回执和集成测试的身份资源。集成包还需用 `python3 tools/gecko/generate_appearance_fixture.py` 生成测试样本。`:app:assembleIntegration` 输出到 `app/build/outputs/apk/integration/`，包名为 `local.pocketchat.test`，使用测试签名。本地编译、设备验收和正式签名分别保留证据。

## 针对性维护测试

日常修改可用已有维护检查器选择受影响的测试。配置备份、下载迁移和浏览器设置可在一条命令中运行。这里的 `JAVA_HOME` 指向 JDK 17，两个 JSON JAR 使用 [完整验收](../.github/workflows/browser-2_1-acceptance.yml) 固定的版本和校验值。

```bash
python3 tools/browser/check_maintenance.py \
  --java-home "$JAVA_HOME" --json-jar "$POCKETCHAT_HOST_JSON" \
  --android-json-jar "$POCKETCHAT_ANDROID_JSON" --output work/quick-stability \
  --only config-backup --only download-library-migration --only browser-preferences
```

维护命令默认按原顺序运行 36 组回归。使用 `--only` 时可选择已有回归或上面的三组专项检查。结果文件记录实际运行的用例和用时。设备和正式发布仍使用对应的完整验收。

## 原签名覆盖安装

以下是普通 Gecko APK 的签名示例。带可选 Chromium 的正式分发使用 `tools/gecko/sign_chromium_release_pair.py`，主包、分包和验收证据须来自同一批构建。

原签名密钥须由维护者提供，保存在 Git 忽略目录，不进入源码、CI 或发布附件。文件名与存放路径不能证明签名身份，必须核对证书指纹。缺少原密钥或证书不匹配时保留未签名包；签名助手会报错，不会生成替代密钥。以下路径是维护者准备原密钥后的示例，不表示工作区已经具备原签名。

在终端运行签名助手时，按提示输入原密钥库和签名密钥的口令。无人值守签名应由私有签名环境注入 `POCKET_STORE_PASSWORD` 和 `POCKET_KEY_PASSWORD`。签名助手只将它们传递给 APK 签名步骤。

```bash
python3 tools/sign-apk.py app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk \
  --key work/release-signing/original-release.jks \
  --tools "$ANDROID_HOME/build-tools/37.0.0" --java "$JAVA_HOME/bin/java"
```

输出 `dist/PocketChat-<version>-gecko-arm64.apk` 和签名检查记录。助手从 `app/build.gradle` 读取本次版本及 versionCode，检查原证书、包名 `local.pocketchat`、非调试构建、无测试入口及 16 KB 对齐。原版证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。不同证书的预览包不能覆盖原版。

## 云环境

已准备工具位于 `work/cloud-setup/jdk/` 与 `work/gecko-sdk-validation/`。`python3 engine-probe/tools/setup.py` 用官方地址与固定校验和准备 SDK 37.1、Build Tools 37、Gradle 和早期验证包所用的 Gecko AAR；它只写忽略目录。该独立验证包保留历史 SDK pin，正式应用 SDK 以 `app/build.gradle` 与上述来源收据为准。

完整验收由 GitHub Actions 构建并核对同批 APK，运行宿主机测试和 Android 设备测试。发布流程另行核对原签名与公网回读，随后推进更新源。

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
