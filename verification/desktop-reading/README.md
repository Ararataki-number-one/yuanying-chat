# 电脑版阅读验证 · 1.5.6 / 32

日期 2026-10-03。本轮保留真实 WebView 与官方网页 UI，新增按环境缩放记忆及键盘输入空间；同时完成内核替换源码评估，没有替换内核或解除 Google 登录限制。

| 检查 | 结果 | 实际范围 |
| --- | --- | --- |
| 阅读控制器 | 28 / 28 | JVM 执行实际 BrowserReading / Policy，使用最小 host doubles 模拟 WebView、事件、偏好与回调；倍率、密度、重开、环境存储、横屏、键盘、真手势、过期回调及登录域名 |
| 输入可见性脚本 | 13 / 13 | jsdom 执行实际脚本，控制几何位置；遮挡滚动、可见时不滚动、正文／代码／草稿／Cookie 不改写、其他域和框架不执行 |
| 桌面 Chromium 布局 | 9 / 9 | Chromium 151.0.7922.173 加载离线样本，360 / 390 / 780 宽度、横屏及缩小高度、代码横向和回复纵向滚动；内容／草稿保留 |
| 原 viewport 脚本 | 12 / 12 | DOM 视口、SPA metadata、双指允许、输入与模型不改写 |
| 显示策略 | 23 / 23 | 原 UA、标签和设置保存守卫 |
| 设置／登录策略 | 36 / 36 | 原任务、代次、身份页及可信 HTTPS 主机策略 |
| Google 拒绝检测 | 17 / 17 | 原检测脚本，不等同于登录成功 |
| 发布和独立测试 APK | 通过 | 资源、Java、D8、原签名、对齐与 1.5.6 / 32；测试组件和 fixture 不进入发布包 |
| Android 阅读回归 | 仅编译 | BrowserReadingRegressionActivity；没有运行测试 Activity 或验证真机软键盘／双指缩放 |
| 真实账号／内核迁移 | 未执行 | 没有取得 Google / ChatGPT 账号，也没有新引擎产物 |

共 **138 / 138** 项已执行主机／桌面浏览器检查。结果在各 `*-results.json`。不是 138 项 Android 真机测试；Chrome 的缩小 viewport 不等同于 Android IME。`built-source-files.json` 记录 app / libs / tests / build.ps1 输入哈希，`artifacts.json` 记录 APK 大小、SHA-256、签名和包信息。

## 复现

从仓库根目录运行，JDK 17 的 `javac` / `java` 需在 PATH：

```bash
mkdir -p work/desktop-reading-validation/host-classes
javac -encoding UTF-8 -d work/desktop-reading-validation/host-classes \
  app/src/main/java/local/pocketchat/BrowserDisplay.java \
  app/src/main/java/local/pocketchat/BrowserReadingPolicy.java \
  app/src/main/java/local/pocketchat/BrowserReading.java \
  tests/browser-reading-host/android/os/SystemClock.java \
  tests/browser-reading-host/android/view/MotionEvent.java \
  tests/browser-reading-host/local/pocketchat/ChatSession.java \
  tests/browser-reading-host/local/pocketchat/BrowserReadingHostTest.java
java -cp work/desktop-reading-validation/host-classes local.pocketchat.BrowserReadingHostTest work/desktop-reading-validation/focus.js
```

DOM / Chromium 检查复用云环境已安装的 jsdom 26.1.0 和 Playwright core 1.57.0，不增加生产依赖。其他机器可在 ignored 工作目录安装这些工具，并调整模块路径：

```bash
javac -encoding UTF-8 -d work/desktop-reading-validation/host-classes \
  app/src/main/java/local/pocketchat/BrowserDisplay.java tests/BrowserDisplayPolicyTest.java
java -cp work/desktop-reading-validation/host-classes local.pocketchat.BrowserDisplayPolicyTest work/desktop-reading-validation/viewport.js
JSDOM_MODULE="$PWD/work/desktop-display-validation/node/node_modules/jsdom" node tests/browser-reading-focus.cjs work/desktop-reading-validation/focus.js
JSDOM_MODULE="$PWD/work/desktop-display-validation/node/node_modules/jsdom" node tests/browser-display-viewport.cjs work/desktop-reading-validation/viewport.js
PLAYWRIGHT_MODULE=/opt/codex/runtimes/cua/lib/node_modules/playwright-core node tests/browser-reading-chromium.cjs work/desktop-reading-validation/viewport.js work/desktop-reading-validation/focus.js
```

`CHROMIUM_PATH` 可指定 Chromium 可执行文件。原设置／Google 策略复现见 [上一轮验证](../browser-settings-login/README.md)。构建见 [说明](../../docs/BUILD.md)。

## 真机核验

1. 原签名覆盖更新；确认旧环境、登录和网络数据仍在。两个环境分别缩放到不同倍率，切换、重开、刷新和重启后分别检查。
2. 360 / 390 / 430dp 手机竖屏与横屏，在默认适应和放大状态检查；刘海、手势导航、三键导航与分屏以实际可用宽度计算。
3. 中文输入、选字、长草稿、系统字体大小和横屏键盘；输入可见且不会清除、发送或改写草稿。收起键盘后五个导航恢复；自动聚焦放大不覆盖倍率。
4. 长回复阅读不自动跳到最下方；代码块左右滑动、选中、复制及外层纵向滑动仍由官方网页处理；双指缩放不吞掉这些手势。
5. “更多 → 网页缩放”与适应屏幕不刷新文档，不改变模型或正在回复的任务；手机版不套用电脑版倍率，切回电脑版仍恢复。
6. Google 登录页使用原显示逻辑，阅读帮助不运行；这版仍可能被 Google 拒绝，不能把状态提示当登录成功。

独立测试包的 `local.pocketchat.test/local.pocketchat.BrowserReadingRegressionActivity` 使用离线样本，结果写到测试包私有目录 `browser-reading-regression.json`，本轮未执行。当前 adb 没有连接设备，云模拟器先前的 WebView 渲染崩溃记录保留，未重复启动并宣称解决。

内核评估与资源／依赖限制见 [迁移方案](../../docs/BROWSER-ENGINE-MIGRATION.md)。Google 登录和新内核集成仍未完成。
