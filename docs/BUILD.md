# 构建 1.5.7

正式应用现已接入 Mozilla 官方 GeckoView。使用 Gradle 构建以合并 SDK 的 Java、原生库、资源、服务和依赖；旧版手工 AAPT2/D8 流程不再适用于本版本。

## 工具与构建

使用 JDK 17、Android SDK Platform 37.1、Build Tools 37.0.0。最低 Android 8，独立环境需要 Android 9。Gradle Wrapper 固定 9.8.0 并校验发行包 SHA-256；AGP 9.4.1、GeckoView 157.0.20260924084938 固定在构建文件。

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

输出 `dist/PocketChat-1.5.7-gecko-arm64.apk` 和签名检查记录。助手检查原证书、包名 `local.pocketchat`、版本号 33、非调试构建、无测试入口及 16 KB 对齐。原版证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。不同证书的预览包不能覆盖原版。

## 云环境

已准备工具位于 `work/cloud-setup/jdk/` 与 `work/gecko-sdk-validation/`。`python3 engine-probe/tools/setup.py` 用官方地址与固定校验和准备 SDK 37.1、Build Tools 37、Gradle 和 Gecko AAR；它只写忽略目录。该脚本名称来自早期验证包，工具也用于正式构建。

本云容器的 Maven Central 返回 429，完整 Gradle 构建通过 `.github/workflows/gecko-integration.yml` 在 GitHub runner 执行。该工作流先校验官方 SDK 和 Gradle，再运行发布编译、Lint 和 Android 15 KVM 回归。不要将本地 javac 成功描述为完整 APK 构建成功。

无需常驻服务即可进行编译。设备回归需要 Android 设备或带 KVM 的模拟器，受控样本与 HTTP/SOCKS 服务由 `tests/gecko/run_device.py` 启动并结束。真实 Google/ChatGPT 登录需要在手机上验收，不在合成样本测试范围内。
