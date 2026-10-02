# 1.5.3 会话与网络界面预览（原版签名）

版本 1.5.3（versionCode 29），更新日期 2026-10-02。

## 下载与覆盖安装

[下载 APK](https://raw.githubusercontent.com/Ararataki-number-one/yuanying-chat/refs/heads/apk/environment-management-preview-20261002/public-downloads/PocketChat-1.5.3-chat-network-preview.apk)，49,370,478 字节。

SHA-256：`3c4719857c358d942a8e1485fced1f5959194f4be7ca10c6634190cc545d8633`。

包名 `local.pocketchat`，使用原发布签名，可覆盖原签名版本。此前临时签名预览包不适用。签名与递增版本号已核对；真实账号覆盖后登录保留仍需手机核验。

## 界面变化

- 会话顶部：汉堡菜单、可切换的环境名称、简洁 / 原网页、更多；第二行只显示真实网络状态并可定位当前窗口。
- 主体继续使用原 ChatGPT WebView，没有把参考 HTML 作为网页，也没有修改官方页面元素。
- 网络只有窗口网络、订阅、出口三栏；无需先切换环境即可编辑窗口。
- 候选配置在保存并应用后才改变连接；自动随机受勾选池约束，手动入口与固定出口独立选择。
- 网络编辑、选择、测速、筛选和详情均使用居中弹窗。

## 验证范围

发布和测试 APK 构建、签名、对齐及版本检查通过。此测试包已生成 78 项通过结果。实际 Mihomo 解析与选择器、真实加密配置保存及跨窗口私有分发的范围详见验证记录。

未完成或无法判定的检查：compact-mode-results.json、compact-mode-restore-results.json、functional-hub-results.json。模拟器 WebView 渲染进程崩溃，网页回归未完成。未连接真机、未登录真实账号；测试代理连接回调与延迟使用隔离夹具，未声称验证私人代理的公开连通性。

[逐文件修改说明](https://github.com/Ararataki-number-one/yuanying-chat/blob/bd8c9c2224711476fedfe4a546d783d935ac280a/docs/CHANGELOG-v1.5.3.md) · [本轮验证](https://github.com/Ararataki-number-one/yuanying-chat/blob/bd8c9c2224711476fedfe4a546d783d935ac280a/verification/chat-network-reference/README.md)

源码提交：`bd8c9c2224711476fedfe4a546d783d935ac280a`；源码分支：`feature/chat-network-reference`。历史 APK 保留，签名密钥没有加入源码或下载附件。
