# 2.0.7 正式版验证记录

发布日期：2026-10-17（UTC）。本版继续完成当前任务中的网络优化与发布要求，沿用会话中明确的发布授权。ARM 真机、真实 ChatGPT 账号和用户公网线路尚未验收；不宣称已达到 200 ms。

## 来源与产物

- 应用源码与发布工具：`0110bf93844fcee4708f25bf8239de888906c269`。
- 冻结 CI 证据：`2698785ed5fd09326c1e38c5edb1ce370d1f3567`。
- 发布产物：`00954a8524a8a74b39e5ea0bcc67b529673b856b`。
- 包名 `local.pocketchat`，版本 `2.0.7`，versionCode `60`，ARM64。
- 文件 `PocketChat-2.0.7-gecko-arm64.apk`，119115144 字节。
- APK SHA-256：`300a3763bc6049d254c188cde63131b37753783fbbf3d558da870c107943809e`。
- 原签名证书 SHA-256：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`，可覆盖安装。

## 已完成验证

- [Android 实际回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38992897864)、[构建、lint 和主机回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38992897933)、[原生网络内核独立重建](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38992897894)全部通过。
- [正式发布流水线](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38995556367)通过，重新核对 APK、证据、源码和原签名。
- 既有五组门槛、15 份实际 Android 报告、四份订阅主机报告通过。附件、下载、网络保护、环境隔离、输入和主题的既有受控检查继续执行。
- 原生网络代码 68 个测试函数通过；另有 7 个函数通过 race 检查，覆盖并发领取、失效和取消。
- 实际 Gecko 经受控认证 SOCKS 链路发起四个独立 HTTP/2 连接，比较一槽和四槽：1 条备用连接：426.0 ms；4 条备用连接：60.0 ms。核对了四个服务端连接编号、完整响应内容、认证和 CONNECT 时序、补充上限及停止后清理。
- 外观与反馈共 17 项 Android 检查、14 次真实屏幕点击；反馈验证预览、目标仓库 URL、正文编码、可排除手机信息和返回后草稿保留。测试拦截外部打开动作，没有向公共仓库提交测试问题。
- 默认分支反馈工作流 `ab6d9d3cf58de5e752e7daffa6bd161e7590d69c` 已部署；[初始化运行](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38991805423)成功，分类和状态标签已建立。分类逻辑的三项主机测试通过，覆盖问题、建议及不执行用户内容。
- 公网匿名完整下载的字节数、SHA-256 和发布清单匹配；Range / If-Range 两段各 1024 字节均为 206，强 ETag 与内容匹配。
- 自动更新清单为 versionCode 60，GitHub latest 指向 `v2.0.7-gecko`。

## 结论与范围

本次改变真实建连路径：固定出口可按需保留最多四条短时认证连接，减少并发新建连接时的握手等待。无备用连接仍直接正常建连；已建立的 HTTP/2、WebSocket 继续复用。每环境最多增加四条短时连接，有资源和少量流量成本，没有定时无限补池。

本地真实 socket 对照约 246 ms → 62 ms，Android 对照数值如上，均是人为设置握手延迟的受控实验，不是用户公网测速。单次线路测速保持原口径；这项优化不会把已经复用连接的物理往返时间从 400 ms 自动变成 200 ms。真实改善仍需同一手机、网络、入口、固定出口和相同操作对比。

没有将模拟器替代 ARM 真机验收，没有记录真实账号登录或用户节点性能为已通过。反馈的最终提交由用户在 GitHub 操作；没有声称自动采纳或无人值守实现建议。

[正式版](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.7-gecko) · [APK 下载](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v2.0.7-gecko/PocketChat-2.0.7-gecko-arm64.apk) · [网络改动范围](NETWORK-BURST-2.0.7.md) · [反馈流程](FEEDBACK.md)
