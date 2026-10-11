# 1.5.17 · 聊天页滚动与输入性能

源码：`90129ac0547f12509f5835ec783ad23b9b49973c`。[逐文件修改说明](../../docs/CHANGELOG-v1.5.17.md)。

[实际构建与 Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38136241373)通过：ARM64 正式包、独立 x86_64 测试包、Lint Vital；156 项主机检查、98 项真实 Android / Mihomo 网络检查、25 项通知检查、78 次浏览器操作、37 张界面对照截图、3 组紧凑顶部性能和真实点击检查、94 项实际 Gecko 长会话检查。

## 确认的性能改动

- 周期性环境核对、心跳写入、地区与延迟解密，以及网络协调器每秒的目录和候选配置读取移至后台。3 组普通/大字体顶部测试中，100 次刷新合并为一次；100 次背景绘制和 6 秒周期更新均没有主线程数据库查询、心跳写入或加密文件读写。未变化的文字和模式背景无重复修改；改名与模式变化仍及时显示。
- 真实 Gecko 对比固定的 1.5.16 脚本，242 条消息和约 10.5 万字当前回复，各采样 12 次。生成观察经真实原生扩展桥的响应总量：2,526,332 → 5,040 字节。DOM 文本读取工作量：2,521,560 → 96 字符。生成时仅检测真实状态；终态完整采集，后续按任务、地址、回复及内容版本复用。
- 实际 Android 滑动、点按和键盘输入进入真实 Gecko；原草稿和受控会话 Cookie 保留，没有自动发送。三次稳定终态和至少两秒窗口后，生产 ChatSession 清除已完成任务，并由生产持久化线程保存完整正文。
- 文件卡片变化、DOM 替换及虚拟化缓存回归继续检查。8 个环境的地区与延迟缓存隔离，替换/删除文件有效；冷路径、热路径 UI 读取均不执行磁盘访问。
- 连续保存配置时，旧候选回调不能清除或应用新候选；穿插测速也不能让保存状态卡住。原网页缩放、真实附件选择、受控图片上传、CSV/Blob 下载、环境删除、配置延后应用和自动更新的既有回归保留。

[完整产物、日志与截图](https://github.com/Ararataki-number-one/yuanying-chat/tree/8d52d882434e06efccd5adcf97864a9c2c54ab50)；[实际 Gecko 性能与语义](gecko-performance-results.json)、[顶部性能](compact-chrome-results.json)、[网络](network-performance-results.json)、[浏览器](device-results.json)、[通知](quiet-notification-results.json)。

## 原签名更新包

[下载正式 1.5.17 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.17-gecko/PocketChat-1.5.17-gecko-arm64.apk)，支持覆盖安装和自动更新。

- 版本：1.5.17 / code 43；大小：120478961 字节。
- SHA-256：`9a59ca8e5511364b01ef19964c1efd9a99068321076d5303d4ff200d50b0b453`。
- 原证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。
- [APK 校验](apk-verification.json)：非调试、排除测试组件与历史脚本、16 KB ZIP 对齐。
- [匿名完整下载](public-download-verification.json)与[公网更新源](public-update-feed-verification.json)确认版本、源码、哈希和签名一致。

## 验证边界

Android 15 x86_64 模拟器、真实 GeckoView 157 / Mihomo / Android 服务和受控网站。长会话数字是检测读取与桥接负担，不能换算成特定真机的帧率或网站速度。两轮帧时间表现不一致：Gecko RAF 平均间隔 31.79 → 28.80 ms，而 Android Choreographer 平均间隔 18.42 → 22.89 ms；这组数据不能证明真机帧率改善。没有连接用户真机和真实账号，不能声称已复现未提供截图或细节的异常画面。
