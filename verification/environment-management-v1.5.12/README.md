# 1.5.12 环境管理与使用体验验证

源码：`16a8fe641c95cff6750f6012e45718b1b345272a`。正式包：`local.pocketchat`，1.5.12 / code 38。

[Release / integration 编译、Lint Vital 与 Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37183539465)通过。105 项主机检查通过：18 项请求生命周期、39 项阅读、10 项 Cookie、23 项更新、15 项地区解析。Android 15 / API 35、x86_64 实际执行 77 次受控操作。

## 此版新增的 Android 验证

- 在真实独立环境进程中保持等待任务，通过生产网络提供者保存新配置；旧线路保持不变，回复结束后自动应用。保存浏览器候选时也不改变正在使用的保护和显示。没有手机 VPN 时保护开关阻断连接。
- 按 Android Home 键进入实际后台，完成合成回复后仍自动应用浏览器设置，清除等待状态和候选配置。
- 原生 Firefox 加载真实 DOM 样本，生产解析逻辑识别内层用户消息编号和当前回复的完成按钮；前一条回复的按钮不能结束当前任务。仅测试副本使用严格限制的本地 origin，正式网页 origin 限制不变。
- 使用 Firefox 官方 privacy API 启用并读取真实抗指纹设置，确认强化保护已启用，再恢复原等级。
- 调用正式删除实现，停止对应浏览器/网络进程，清除环境偏好与加密私有数据，正确删除失效浏览器锁链接，保留其他环境和已保存文件。复用已删槽位后，旧受控 Cookie 不存在；仍存活的管理进程读到新的空偏好，旧缓存不回写。
- 删除默认环境后，其他环境、全局更新偏好、共享订阅缓存与固定出口仍在；默认入口重新分配，最后一个环境受到保护。

原有受控网页隔离、HTTP/SOCKS 线路、上传/下载、Cookie 与 SDK 状态恢复、横竖屏、60%～130% 缩放、可信屏幕触摸和键盘输入、页面关闭恢复，以及实际更新下载和系统安装确认入口继续通过。逐项数据见 `device-results.json` 和 `device-native-events.txt`。

## 正式包与公网

原签名 APK：`PocketChat-1.5.12-gecko-arm64.apk`，120450289 字节，SHA-256：`67ee5bf41b80f739c30f74853a904628e1269b9ec0ecff7f9b6b6f932e0a81a7`。证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。非调试、无测试组件、16 KB ZIP 对齐。公网匿名完整下载通过，自动更新源的版本、字节数、哈希与公开 APK 一致。

[下载 1.5.12 正式 APK（ARM64）](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.12-gecko/PocketChat-1.5.12-gecko-arm64.apk)。

## 验证边界

测试数据为合成内容，未使用真实 Google / ChatGPT 账号或 ARM 手机。真实账号长期登录、真实生成文件链接、手机版偶发白屏和厂商后台策略仍需真机复核。地区解析验证覆盖节点名称；公开 GeoIP 请求未由本地测试访问真实线路。手机 VPN 测试覆盖未连接时阻断，连接后拔掉 VPN 的真机行为尚未验收。测试不代表所有协议无泄漏，也不能延长网站的登录有效期。
