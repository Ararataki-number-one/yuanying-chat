# 覆盖更新回归

此独立 instrumentation APK 用原版密钥签名，运行在已安装的真实发布 APK 内。它通过应用自身的存储实现写入、读取样本 Cookie、共享环境目录、各环境偏好、会话草稿、消息缓存、加密记录与文件。测试安装新版时使用 `adb install -r`，不卸载或清除基线应用数据。

仅支持一次性 Android 模拟器：工具检查 `ranchu/goldfish` 硬件和显式 `allowFixtureWrites` 参数。**运行器在每个独立用例开始时重置模拟器里的 `local.pocketchat`**，不要将其用于真实手机或真实账号。两个基线分别为历史 v1.5.0（目录 v3）和上一轮原签名预览包（目录 v4）。

在已经准备好 JDK/SDK 的当前云环境：

```bash
python3 tests/upgrade/build.py
python3 tests/upgrade/run.py
```

需要预先准备 `work/signature-check/YuanyingChat-v1.5.0-original.apk`、`dist/PocketChat-1.5.0-environment-preview-original-signature.apk`、`dist/PocketChat-1.5.1.apk`，以及忽略目录中的原版 `local-test.jks`。构建读取密钥密码环境变量 `UPGRADE_QA_SIGN_PASS`，当前测试密钥使用仓库原有的默认参数。发布 APK 不包含此测试组件。

结果位于 `work/upgrade-qa/results/`。只有新结果文件生成、全部检查项为 `pass: true`、没有 `error` 且安装确实成功才算通过。真实账号会话是否被网站继续接受，仍需真实手机与账号验证。
