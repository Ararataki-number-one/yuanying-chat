# 1.5.19 · 聊天交互与更新续传

源码：`5fd4c645e735eed356bd18560283afb4e71a553d`。[逐文件修改说明](../../docs/CHANGELOG-v1.5.19.md)。

[构建与实际 Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38163201833)通过：正式 ARM64 包、独立 x86_64 验证包、Lint Vital、261 项主机检查、128 项 Gecko 长回复与恢复检查、143 项真实 Mihomo 网络检查、28 项更新传输检查、25 项通知检查、83 次浏览器操作、37 张界面对照截图与 3 组紧凑顶部检查。

## 实际验证

- [更新续传](update-transfer-results.json)：合成已签名 APK 经真实 HTTP 和生产 JobScheduler 下载；断半保留进度，重新请求剩余字节；真实暂停、重建界面、强制停止进程后继续；原 SHA、大小、安装身份和签名一致。已暂停的真实半包在取消后阻塞清理 worker，确认取消标记真实落盘，再杀进程；新 PID 清理残留，后续请求从零开始，无 Range/If-Range。此项明确不声称杀死活动写线程。服务器忽略 Range 时从零重新下载；范围、ETag、长度、SHA 或签名异常均拒绝安装。保存请求 trace 与真实 Android 操作记录。旧系统下载查询在取得真实 cursor 后阻塞，实际取消后再放行；迟到结果不覆盖已取消状态，旧系统任务行实际删除且不重新启动。
- [原生浏览器](device-results.json)：正常系统栏可见、安全区匹配，IME 隐藏且布局连续稳定至少 1 秒后执行 3 次真实 Android 手势；每次触摸的实际位置、安全区与尺寸均保持稳定时，手动表面同步从逐事件改为一次。实际移动后点击和输入仍正确，文档和完整草稿保持。300k 状态在后台序列化，1000 次待写合并保留最后一次；后续无效状态保留最新有效状态，持续更新也定期落盘，独立环境不混用。
- [线路调度](network-performance-results.json)：繁忙及排队后变繁忙的自动探测请求为零，空闲后得到真实样本；已有新样本时不重复测。实际故障恢复只核验一次，受保护 WebSocket 保持同一连接连续收发。核验服务在 TLS 请求后发生真实 RST / EOF 时，已有同身份核验凭据的 WSS 继续收发，PID、入口、控制密钥摘要和核心代号不变；同样故障下首次和换线路仍拒绝，发送前核验仍失败。取消、TLS 身份错误、真实核心死亡与不一致出口仍阻断。
- [交互调度](interaction-host-results.json)：终态读取延后时不传半成品或积累完成样本；最终完整正文、代码、附件、输入、登录与无重发保持；混合 DOM 变化准确失效；无关点击不遍历整页，缩放事件合并且后台保存最终值。真实输入先确认 IME 可见以及输入框、光标和视口连续稳定至少 600 ms，再执行一次完整 Android 输入 burst；受信任按键顺序与原草稿均严格验证。正式验收明确关闭额外 SDK / IME 包装、DOM 选择写入观察与 evaluate 日志，不能以带诊断观察的通过结果替代正常路径。既有长回复、下载、图片选择、隔离、升级和通知回归保留。

完整界面截图保存于[不可变 Android 验证产物](https://github.com/Ararataki-number-one/yuanying-chat/tree/a207270efb6f69f9a0c35f1091a4ca54b9bc0a90/ui-visuals)。

## 受控网页开销对比

[真实 Chromium 对照](focused-results.json)交错执行 6 轮，同样 4 倍 CPU 限速、240 条历史与 110k 正文：无关点击捕获处理延时中位数 32→0.1 ms，MutationObserver 自身耗时中位数 258→53 ms。每版本 60 次真实按钮手势，80 批次 / 14080 条变化。全部正文、代码、草稿保留，零发送 intent。固定旧源码与[本版脚本 SHA](focused-source-files.json)可核对，[复现实验](focused.py)保留。这些指标是受控 Chromium 工作量，不是用户手机 Gecko 帧率或网络速度。

## 原签名安装包

[下载正式 1.5.19 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.19-gecko/PocketChat-1.5.19-gecko-arm64.apk)，支持覆盖安装和应用自动更新。

- 版本：1.5.19 / code 45；大小：120499441 字节。
- SHA-256：`545c943ac22c84a1d2bb80143c3c4a2b53c6446919abe77c2a3d808aaeac4675`；原证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。
- [APK 校验](apk-verification.json)、[匿名完整下载](public-download-verification.json)、[公网更新源](public-update-feed-verification.json)与[官方 CDN 分段请求](public-range-verification.json)。
- [同源码发布门槛](release-evidence.json)要求所有实际回归与安装包来自同一源码；原密钥没有进入 CI 或公网。

## 验证边界

曾在两次未加额外诊断的硬件按键回归中观察到光标回退、字符错位；带原生诊断的三次通过不能证明其已修复，尚未归因，也没有把未经验证的 SDK 补丁加入正式包。最终正常回归的通过只代表该次执行通过，不能排除这一偶发现象。

实际 Android 15 x86_64 模拟器、GeckoView、Mihomo、JobScheduler 与合成网站/APK；没有连接用户真机或真实账号。新表面同步手势使用受控短网页，验证触摸/输入和坐标正确性，不代表长 ChatGPT 网页的真实滚动帧率。峰值下载速度、网站响应和手机/电脑差异仍取决于线路、设备及服务器，未做同 Wi-Fi/同入口/同出口真机对比。续传减少重复传输；聊天后台调度减少资源争抢，不能据此承诺固定的网速或延迟提升。
