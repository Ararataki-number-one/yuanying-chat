# 1.5.18 · 网页连接与提问恢复

源码：`c85c84396f8afca78ffe266faf8556dc6acb5980`。[逐文件修改说明](../../docs/CHANGELOG-v1.5.18.md)。

[实际构建与 Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38141104409)通过：ARM64 正式包、独立 x86_64 测试包、Lint Vital；197 项主机检查、126 项真实 Android / Mihomo 网络检查、25 项通知检查、78 次浏览器操作、37 张界面对照截图、3 组紧凑顶部与真实点击检查、125 项实际 Gecko 长会话和恢复检查。

## 实际验证

- DOM 全部暂时移除、单独虚拟化原提问、恢复空壳和正常首页分配对话地址：保留原等待任务；真实切换对话、正文变化仍拒绝错误绑定。恢复不自动发送。
- 仅当前有效网页连接错误影响任务。历史回复、用户引用、代码和无关重试按钮不影响当前回复。连接错误及页面加载清除完成样本，恢复后重新满足三次稳定采样和至少两秒。
- 主动恢复先持久化草稿。写入期间产生新输入或新等待任务，实际 Gecko 回归确认取消过时重载，保留最新输入和任务；受控登录 Cookie 不清除。
- 真实 TLS WebSocket 经 Mihomo 的入口和固定出口两段 SOCKS 连续通信。核验服务 HTTP 故障、真实读取超时、无效响应期间，同一已核验核心和线路仍通信；正式独立网络服务的 PID、代数、配置和端口保持一致。故障核验返回失败并退避，不声称新核验成功。
- 新路线、首次连接、取消期间切换到未核验入口，以及实际出口不一致仍阻断；真实出口不一致时即便维护操作并发取消，正式网络服务仍停止核心和长连接。
- 既有图片选择与上传、生成文件下载、缩放、环境编辑删除、延后应用、自动更新、通知及性能回归保留。

[完整产物与日志](https://github.com/Ararataki-number-one/yuanying-chat/tree/3758bf1f0a539119c0222e7bda198b37645400bb)；[Gecko](gecko-performance-results.json)、[Mihomo](network-performance-results.json)、[发布证据门槛](connection-evidence.json)。

## 原签名更新包

[下载正式 1.5.18 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.18-gecko/PocketChat-1.5.18-gecko-arm64.apk)，支持覆盖安装和自动更新。

- 版本：1.5.18 / code 44；大小：120487153 字节。
- SHA-256：`acb5abd7f9be2ae2dbcd2032b4d649cb9943f1b550496cc0baea71110e697d4c`。
- 原证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。
- [APK 校验](apk-verification.json)：非调试、排除测试组件与历史脚本、16 KB ZIP 对齐。
- [匿名完整下载](public-download-verification.json)与[公网更新源](public-update-feed-verification.json)确认版本、源码、哈希和签名一致。

## 验证边界

Android 15 x86_64 模拟器、真实 GeckoView / Mihomo / Android 服务和受控网站。没有连接用户真机或真实账号；不代表已复现截图中的网站工具服务器故障。客户端修复应用侧断链诱因，提供保留草稿的主动恢复，不能保证消除网站服务器内部的所有 WebSocket 故障，也不自动重试网站任务或重发问题。
