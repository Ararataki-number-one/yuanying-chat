# 本次环境管理调整的验证

日期：2026-10-02。Android 15 AOSP x86_64 模拟器，WebView 124.0.6367.219，JDK 17、SDK 35、Build Tools 35.0.0。

| 检查 | 结果 |
| --- | --- |
| 普通 APK 构建、签名、对齐与包信息 | 通过 |
| 独立测试 APK 构建、签名、对齐与包信息 | 通过 |
| 环境列表与目录迁移 | 18 / 18，通过；见本目录 JSON |
| 启动与默认环境路由 | 10 / 10，通过；见本目录 JSON |
| 含 WebView 的界面回归 | 未完成，待稳定设备复核 |

界面回归曾遇到 WebView 渲染进程 `SIGTRAP`，并观察到模拟器 System UI 无响应。当前机器没有 `/dev/kvm`，采用软件模拟。模拟器 Wi-Fi 连接和较低分辨率已用于排查；没有放宽断言、沿用历史结果或把未生成结果文件的运行计为通过。

未登录真实账号，未验证真实账号下的登录、发送和下载行为。本目录与旧版 `validation-summary.json` 分开保存。

## 在设备上复核

安装独立测试 APK。每个测试开始前停止测试包，并删除该测试的旧结果，然后启动对应 Activity：

```bash
adb install -r -g dist/PocketChat-tests.apk
adb shell am force-stop local.pocketchat.test
adb shell run-as local.pocketchat.test rm -f files/design-ui-results.json
adb shell am start -n local.pocketchat.test/local.pocketchat.DesignUiTestActivity
adb exec-out run-as local.pocketchat.test cat files/design-ui-results.json
```

等待当前 JSON 文件生成并检查每项 `pass`。没有文件、没有检查项或存在 `error` 均不算通过。环境列表与启动测试分别为 `WindowHomeTestActivity` / `window-home-results.json`、`DesignLaunchTestActivity` / `design-launch-results.json`。列表测试会重建**独立测试包**的环境目录，只用于隔离回归。
