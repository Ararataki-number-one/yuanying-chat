# 浏览器设置与登录提示验证 · 1.5.5 / 31

验证日期：2026-10-03。本轮处理保存守卫误把瞬时状态当成任务，以及登录页被当成网络失败的问题；Chrome 插件开发暂停。

| 检查 | 结果 | 实际范围 |
| --- | --- | --- |
| 显示策略 | 23 / 23 | JVM 执行实际 BrowserDisplay；UA、显示名称、保存 guard 和视口策略 |
| 设置／登录策略 | 36 / 36 | JVM 执行实际 BrowserSettingsPolicy 和 LoginPagePolicy；真实任务保护、代次／页面绑定、HTTPS 身份域名与伪造地址拒绝 |
| Google 拒绝检测 | 17 / 17 | jsdom 执行实际生成脚本，文案检测、错误密码不误判、页面和输入字段不变、只返回布尔值、其他域和子框架不触发 |
| 发布和独立测试 APK | 通过 | 资源、Java、D8、原签名、对齐与版本；签名密钥未公开 |
| 原生保存流程用例 | 仅编译 | BrowserSettingsRegressionActivity 使用拦截网页检查保存、缓存忙碌、pending 保护、旧回调和 WebView 复用；本轮未执行 |
| 真实 Google / ChatGPT 账号 | 未验证 | 没有登录账号，没有解除 Google WebView 限制或完成设备端复现 |

结果在 `display-policy-results.json`、`login-settings-policy-results.json`、`google-dom-results.json`。`built-source-files.json` 和 `artifacts.json` 记录编译输入及产物。

## 复现主机检查

```bash
mkdir -p work/browser-login-validation/policy-classes
javac -encoding UTF-8 -d work/browser-login-validation/policy-classes app/src/main/java/local/pocketchat/BrowserDisplay.java app/src/main/java/local/pocketchat/BrowserSettingsPolicy.java app/src/main/java/local/pocketchat/LoginPagePolicy.java tests/BrowserDisplayPolicyTest.java tests/LoginSettingsPolicyTest.java
java -cp work/browser-login-validation/policy-classes local.pocketchat.BrowserDisplayPolicyTest work/browser-login-validation/viewport.js
java -cp work/browser-login-validation/policy-classes local.pocketchat.LoginSettingsPolicyTest work/browser-login-validation/google-blocked.js
npm install --prefix work/browser-login-validation/node --no-audit --no-fund jsdom@26.1.0
JSDOM_MODULE="$PWD/work/browser-login-validation/node/node_modules/jsdom" node tests/login-page-detection.cjs work/browser-login-validation/google-blocked.js
```

云环境本轮复用了上一轮已安装的 jsdom 26.1.0，未增加项目生产依赖。APK 构建见 [说明](../../docs/BUILD.md)。原生用例需在设备上运行独立测试包的 `local.pocketchat.test/local.pocketchat.BrowserSettingsRegressionActivity`，结果文件位于该测试包私有目录 `browser-settings-regression.json`；未执行结果不计入 76 项。

## 设备核验

1. 覆盖安装原签名包，确认原环境和账号数据仍存在。
2. 普通加载、连接和等待重连期间修改手机版／电脑版，确认不再出现笼统“未完成操作”；旧回调不得改变保存后的选择。
3. 实际发送、网页回复、上传和下载期间修改设置，确认具体阻塞原因且原任务保持。
4. 网页有草稿时保存，确认重新加载后文本及阅读位置可恢复；草稿读取、归档失败时不应用。
5. Google 普通登录、明确浏览器拒绝、密码错误和网络失败分别检查；登录等待不能变为网络故障，真正的网络失败保留。
6. 拒绝帮助每页面只自动显示一次，更多菜单可重开；返回 ChatGPT 使用真实网页。外部浏览器入口不传递 OAuth 参数、Cookie 或本环境代理配置，也不宣称会话同步。

Google 官方帮助和政策页面在本环境的公开访问返回网络代理 403，未声称成功读取最新政策；可访问的 [AppAuth Android 文档](https://github.com/openid/AppAuth-Android)明确其 OAuth 授权使用浏览器／Custom Tabs，不支持 WebView。本 App 使用第三方 ChatGPT 站点登录流程，不能仅接入 AppAuth 就保证获得相同站点会话。截图与当前 WebView 架构符合应用内浏览器拒绝这一判断，但真实账号仍需手机验证。

上一轮云模拟器渲染崩溃和网络恢复耗时失败保留在 [历史验证](../chat-network-reference/README.md)；本轮没有重跑或声称解决。
