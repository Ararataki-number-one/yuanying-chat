# 环境网页显示验证 · 1.5.4 / 30

验证日期：2026-10-03。本轮新增手机版 / 电脑版环境配置，未重新实现网络核心或 ChatGPT 页面。

| 检查 | 结果 | 范围 |
| --- | --- | --- |
| 浏览器策略 | 23 / 23 | JVM 执行实际 BrowserDisplay 类，访问标识、版本、标签、忙碌状态和视口策略 |
| 网页视口 | 12 / 12 | jsdom 执行实际生成脚本；仅 DOM，包含标题、正文、模型、输入、消息及 Cookie 保持 |
| 环境迁移 | 8 / 8 | 主机 SQLite 执行 v4 / v5 实际建表和升级 SQL，旧字段及草稿保留、每环境独立保存 |
| 发布和独立测试 APK | 通过 | Java / 资源 / D8 编译、原签名核验、zipalign 和包版本；编译测试包不等于执行原生用例 |
| Android WebView 与真实账号 | 未执行 | 本轮未连接真机，布局、缩放、键盘、跨进程配置和登录保持均需设备核验 |

结果分别在 `policy-results.json`、`viewport-results.json`、`migration-results.json`。`artifacts.json` 记录 APK 哈希、大小、版本和签名证书；`built-source-files.json` 记录编译输入文件哈希。签名私钥未纳入验证材料。

## 复现主机检查

使用 JDK 17、Python 3、Node.js 和 jsdom 26.1.0。在仓库根目录运行；下面目录可任意替换：

```bash
mkdir -p work/desktop-display-validation/policy-classes
javac -d work/desktop-display-validation/policy-classes app/src/main/java/local/pocketchat/BrowserDisplay.java tests/BrowserDisplayPolicyTest.java
java -cp work/desktop-display-validation/policy-classes local.pocketchat.BrowserDisplayPolicyTest work/desktop-display-validation/viewport.js
npm install --prefix work/desktop-display-validation/node --no-audit --no-fund jsdom@26.1.0
JSDOM_MODULE="$PWD/work/desktop-display-validation/node/node_modules/jsdom" node tests/browser-display-viewport.cjs work/desktop-display-validation/viewport.js
python3 tests/browser-display-migration.py
```

APK 构建见 [构建说明](../../docs/BUILD.md)。本轮原生创建表单用例补充在 `WindowHomeTestActivity`，仅完成编译，不计入 43 项已通过检查。

## 手机核验清单

1. 原签名覆盖安装，确认旧环境、分组、草稿和登录仍可用，旧环境显示方式为手机版。
2. 新建环境选电脑版，确认页显示选择；返回前页选择保留；取消创建不写入环境配置。
3. 一个环境设电脑版，另一个保持手机版；依次打开并重启应用，确认各自选择独立保留。
4. 已有环境编辑：取消和存草稿保持当前页面，保存环境才重新加载；手机版 → 电脑版 → 手机版后恢复布局。
5. 原网页核验：官方输入框、模型选择、消息、侧栏正常；双指缩放、横竖屏、键盘和底部安全区可用。
6. 网页有未发送草稿时修改显示方式，确认文本及阅读位置恢复；归档失败或状态改变时提示且不应用。
7. 回复、提交、附件上传、连接、导航或恢复进行中，修改显示方式应提示等待，已有任务继续。
8. 分别检查兼容、标准、强化保护；保留简洁 / 原网页功能及当前环境网络配置。

上一轮 [会话与网络验证](../chat-network-reference/README.md) 包含云模拟器 WebView 渲染崩溃及恢复耗时检查失败的证据；本轮没有重跑这些设备检查或声称修复。主机 DOM 的 Cookie 保持检查不能证明真实账号覆盖安装后登录保持。
