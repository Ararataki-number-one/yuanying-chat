# 构建

源码使用 Java、Android SDK 35 与 PowerShell 构建。最低安卓版本为 8.0；新增独立窗口需要安卓 9 或以上。内置网络组件支持 ARM64 和 x86_64。

## 准备工具

在 Windows 上安装 PowerShell、JDK 17、Android SDK Platform 35 和带有 AAPT2、D8、zipalign、apksigner 的 Android SDK Build Tools。

将工具放成以下结构，或者用 `-ToolsRoot` 指定同样结构的已有目录：

```text
work/android-tools/
  java/<JDK 17 目录>/
  build/<Build Tools 目录>/
  platform/<Android 35 Platform 目录>/
```

`libs/` 和 `app/src/main/jniLibs/` 已包含当前版本使用的库与内置网络二进制。

## 构建发布包

从仓库根目录运行：

```powershell
./build.ps1 -ToolsRoot 'D:/AndroidTools'
```

结果是 `dist/PocketChat-1.5.6.apk`。临时输出位于 `work/android-test/`。

首次构建会在 `work/android-test/private/local-test.jks` 创建本地签名密钥。该目录被 Git 忽略。

发布版本的原签名密钥不在仓库。自行生成的不同签名安装包不能直接覆盖已安装的官方发布包；需要覆盖更新时必须使用同一原签名。

使用原密钥时，将它放在被 Git 忽略的 `work/android-test/private/local-test.jks`，替换自动生成的测试密钥并妥善保留原文件。本次云环境已配置用户提供的原密钥；Windows 与云环境构建助手都读取该路径。密钥文件不属于发布附件或源码。

## 独立测试包

```powershell
./build.ps1 -Test -ToolsRoot 'D:/AndroidTools'
```

生成 `dist/PocketChat-tests.apk`，测试包名为 `local.pocketchat.test`，与发布版分离。测试 Activity 与网页样本位于 `tests/`，发布构建不会包含测试组件。

测试样本拦截网页请求，不需要登录真实账号。网络出口公开服务测试需要单独明确发起，不属于默认本地回归。

本轮逐项结果见 [电脑版阅读验证](../verification/desktop-reading/README.md)，旧版本记录单独保留。

`-Development` 只用于本机调试。`-Personal` 依赖未公开的个人预设打包器；普通发布版无需该功能，也不包含个人网络参数。

## 已准备的 Codex Linux 环境

云环境保留了 JDK 17、Android SDK 35 和 Build Tools 35.0.0。原 `build.ps1` 使用 Windows 可执行文件名和分隔符；Linux 适配助手在 Git 忽略的 `work/cloud-setup/` 中，按相同资源、Java、D8、打包与签名流程构建，不修改仓库依赖。

```bash
cd /workspace/yuanying-chat
python3 work/cloud-setup/build.py release
python3 work/cloud-setup/build.py test
```

构建输出与上述 Windows 命令相同。助手会校验 APK 签名、对齐和包信息。这些助手随已准备的云环境保留，普通源码克隆仍以 Windows 构建说明为准。编译独立测试 APK 不等于执行测试 Activity；设备回归需要 Android 设备或模拟器。
