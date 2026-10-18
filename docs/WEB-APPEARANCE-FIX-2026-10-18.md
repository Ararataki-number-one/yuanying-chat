# ChatGPT 网页主题同步修复

状态：源码修复完成，尚未打包或发布新 APK。

用户报告应用外层为深色、ChatGPT 网页仍为亮色。原实现只在原生主题通知、DOMContentLoaded 和 pageshow 时设置网页根元素；页面后续初始化或单页导航重新写入亮色时没有持续同步。

修复沿用网页的 light/dark 类和 color-scheme，不替换官方页面或样式表：

- document_start 读取 Gecko 已设置的颜色偏好，在原生消息到达前同步主题。
- 仅监听 html 的 class、style，以及 document 的直接子节点；修复后续覆盖和根元素替换。
- 使用幂等写入，避免监听器自触发循环；不扫描回复、消息列表或输入框。
- pagehide 断开观察，pageshow 恢复；只对 https://chatgpt.com 的顶层页面生效。

验证：原有 25 项检查通过。新增 6 项 JSDOM 生命周期测试全部通过；用发布版旧脚本执行同组测试，5 项失败，确认覆盖了原先遗漏的情况。验证了计算后的前景/背景色、首次加载、延迟初始化、单页导航、根元素替换、系统主题变化、页面恢复、登录域隔离、草稿/光标和 Cookie 保持。连续 300 次回复内容更新不触发主题观察回调，主题恢复后没有持续自触发回调。

新增测试接入主机与 Android 集成工作流。测试使用受控 DOM 和样式，不代表已验证真实 ChatGPT 登录后的页面、ARM 手机或网页截图；本次尚未执行新的 Android 构建或发布。

本地执行：

```sh
node tests/appearance_web_test.js
JSDOM_MODULE="$PWD/work/appearance-host/node_modules/jsdom" node --test tests/appearance_lifecycle_test.cjs
```
