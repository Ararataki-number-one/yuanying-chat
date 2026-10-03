# Android 电脑版 Chrome 扩展可行性 · 2026-10-03

本轮是内核源码、项目依赖及构建资源评估。**没有实现扩展模式，没有安装扩展，没有编译新内核或发布新 APK。** 应用源码、版本、WebView 生命周期、登录目录、网络核心和后台服务未修改。

`assessment.json` 记录当前空间、12 个直接依赖 WebView 的应用文件、官方源码快照和未执行项目。`source-fetches.json` 保存成功与失败的公开文档访问状态及哈希；源码均在被 Git 忽略的 `work/chrome-extension-assessment/` 中，未整份复制第三方源码到项目。

## 核实结果

- Chromium 提供 Android 桌面扩展的源码开关。检查了 `cc2df82017e1a381bbf9e19b438c1ef7bb82695e` 的扩展构建标志和 Chrome 构建参数。注释仍说明部分代码尚未移植；此检查不是扩展可用性测试。
- 同一 Chromium 提交的官方 Android 构建文档要求至少 100 GB 空闲磁盘。当前记录约 26.4 GiB，低于最低要求；没有尝试不完整核心构建。
- GeckoView 官方安装接口说明 `.xpi` 和 Mozilla 签名要求，不能用作直接 `.crx` 兼容证明。
- Kiwi 上游 README 明确归档且 2025 年 1 月后不维护。
- `mises-id/mises-browser` 的所取默认分支提交为 Chromium 77 的旧 Kiwi 源码，未采用。
- Dark Reader 的 Chrome MV3 manifest 和 uBlock Origin Lite 的官方 README 已读取；Tampermonkey README 明确公开仓库仅含旧版源码，当前发行包未取得或执行。

## 未完成检查

Chromium 核心编译、ARM64 手机上安装和运行、三个扩展真实兼容性、扩展弹出页与权限、profile 隔离、扩展后台网络路由、登录和数据兼容、附件下载、回复观察、草稿恢复及后台服务均未执行。没有通过的运行用例或测试计数。

Google Chrome 商店帮助、Mozilla Javadoc 站点和 GitHub API 的部分请求被网络代理以 403 拒绝；改用可访问的公开 Git 与 raw GitHub 源码完成相应阅读。此处的 403 是网络访问结果，不是用户权限批准或插件兼容性结论。

## 复查方法

从仓库根目录运行 `df -h /workspace` 和 `rg -l 'android\.webkit|androidx\.webkit' app/src/main/java/local/pocketchat`，检查当前空间和耦合范围。空间随运行变化，以 `assessment.json` 的字节值为当次记录。源码 URL 与 SHA-256 在证据 JSON 内；官方商店插件版本须在实际安装测试时重新固定。

功能入口、三款样本、迁移步骤和下一步要求见 [方案](../../docs/ANDROID-DESKTOP-EXTENSIONS.md)。
