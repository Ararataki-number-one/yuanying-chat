# 1.5.14 网络底层升级与验证

正式源码：`32fe89eae00471513b2ea9cf9e52a86bf601804d`。包名：`local.pocketchat`，1.5.14 / code 40。设计见 [底层架构](../../docs/NETWORK-ARCHITECTURE.md)、[性能策略](../../docs/NETWORK-PERFORMANCE-PLAN.md)；[逐文件修改](../../docs/CHANGELOG-v1.5.14.md)。

## 编译与实际执行

[完整构建与回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37200355697)通过，包括 ARM64 正式 APK、x86_64 独立测试 APK 和 Lint Vital。105 项既有主机检查通过：18 项请求生命周期、39 项阅读、10 项 Cookie、23 项更新、15 项地区解析。Android 15 / API 35 实例实际执行 [65 项网络检查](network-performance-results.json)、[77 次浏览器操作](device-results.json)。

网络使用正式 Mihomo 内核、两个本机 SOCKS 跳和独立 HTTPS 样本。HTTPS 合成证书仅在测试包受信任，正式 APK 不含测试证书或测试组件。检查包含：

- 允许池和跨订阅约束、旧随机与手动模式保持、持续优选、冷却与忙碌延后。
- 首次 / 复测真实 HEAD、同一连接复用、候选使用新连接且不修改当前入口、固定出口一致、网站限制不冒充断线。
- 真实 DNS A 查询、交易标识和响应验证、24 小时有效期、按环境隔离、取消中的请求不覆盖当前连接。
- 独立服务和真实内核 PID；控制客户端重建后接管同一 PID / 端口并重新核验出口，恢复准确的入口索引。
- 实际结束另一环境的控制进程，代理内核继续运行；实际结束单个内核，退出事件到达客户端，另一环境仍可用。
- 新实例不受旧退出事件影响；停止确认、独立停止；实际结束网络服务进程后准入失效，再启动新服务并核验恢复。

受控线路的首次网站响应为 161 / 70 ms，复测为 4 / 2 ms。样本具有合成入口等待和目标响应时间，只证明测速、隔离和复用行为；不代表真实 ChatGPT 或用户线路的测速结果，也不作为速度提升百分比。

既有浏览器操作继续覆盖独立登录存储、重启 / 前后台恢复、缩放、附件与下载、受控 HTTP / SOCKS 线路、回复期间保存配置、后台应用、删除与自动更新。受控系统安装器已打开，没有安装合成升级包。

## 原生界面

[原生报告](ui-visual-results.json)包含 30 张既有界面截图和 3 张新增模式截图，均保留对应控件树。既有对照只恢复八个视觉源文件，其他核心源码与测试签名相同，正式 ARM64 APK 始终由当前源码构建。新增模式在正常字体下实际点击随机 / 手动 / 优选，确认控件类型和选项切换。

| 新增模式 | 原生画面 |
| --- | --- |
| 360 × 640 dp / 普通字号 | [查看](ui-visuals/network-latency-360-font1.png) |
| 412 × 640 dp / 普通字号 | [查看](ui-visuals/network-latency-412-font1.png) |
| 360 × 640 dp / 字体 200% | [查看](ui-visuals/network-latency-360-font2.png) |

已人工检查上述三个画面：普通字体三个模式可见，大字体页签横向滚动；节点列表可滚动，主要按钮与关闭操作可见。网络卡片保持原有密度，辅助检测放在详情与测速结果。

## 原签名与公网

[下载正式 APK（ARM64）](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.14-gecko/PocketChat-1.5.14-gecko-arm64.apk)。可以覆盖原签名版本，应用自动更新源已指向 1.5.14。

- 文件：`PocketChat-1.5.14-gecko-arm64.apk`，120462577 字节。
- SHA-256：`1f9c034a1dc41b816bbe56e20b541e0bbe3136e13bfda3bb0ddec7e12d924b54`。
- 原证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。
- 非调试、无测试组件 / 合成 TLS 资产、16 KB ZIP 对齐，见 [APK 校验](apk-verification.json)。
- [发布任务](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37201252668)通过；[公网匿名完整下载](public-download-verification.json)和[自动更新源](public-update-feed-verification.json)的源码、版本、字节数、哈希、原证书一致。

## 边界

没有真实账号、用户订阅或 ARM 手机。真实网站的验证限制、长期登录、真实线路延迟与厂商后台策略仍需真机实测。独立服务保留代理内核及其缓存，不能让已死亡浏览器进程持有的 HTTP 请求继续执行。控制面和管理界面仍保留现有轮询；退出监督与服务 IPC 使用状态事件。配置或固定出口不一致时不会接管旧内核，不回退直连。
