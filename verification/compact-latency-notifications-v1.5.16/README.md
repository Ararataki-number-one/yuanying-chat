# 1.5.16 · 实测延迟、紧凑顶部与完成提醒

源码：`380d15013559f63d7325bb779268ee9180585953`。逐文件说明见 [修改说明](../../docs/CHANGELOG-v1.5.16.md)。

[完整构建与 Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38124683307)通过。正式 ARM64 APK、独立 x86_64 测试包、Lint Vital 完成构建；105 项既有主机检查、82 项真实 Android / Mihomo 网络检查、25 项真实 Android 通知检查、78 次浏览器操作，以及 37 张界面对照截图、3 张网络模式和 3 组紧凑顶部验证通过。

## 本轮验证

- 当前已恢复线路缺少读数时，回复过程中也会补测真实小请求；保持入口、固定出口、连接世代和代理内核运行。频率有上限，不扫描其他节点。显示探测失败不会冒充整个网络断开。
- 应用代理 / 手机网络通过既有受保护路线得到连接响应；网络保护阻止请求时没有直连回退。历史读数有“上次”标记；真实健康失败仍可见。
- 360 / 412 dp 宽度、普通与 2 倍字体检查：普通顶部约 58 dp，模式/延迟/状态完整，长环境名称省略。圆点保持可见；五个按钮使用真实 Android 点击，触控区域至少 48 dp。网络行及“已连接”真实点击均无导航或操作。
- 旧渠道及普通进度通知先证实出现，再验证升级清除。后台回复与连接服务真实运行，切到 Home 后仍检测；生产稳定终态检测只提醒完成，按环境与回复持久去重；旧去重记录与关闭/重开提醒兼容。
- 既有网页登录存储隔离、缩放、附件选择和受控图片上传、CSV / Blob 下载、恢复、延后应用网络配置、环境删除和自动更新回归继续通过。

[完整产物与截图](https://github.com/Ararataki-number-one/yuanying-chat/tree/b64281925da60f772716874adf37c53e5ff09e87)。详见 [网络](network-performance-results.json)、[通知](quiet-notification-results.json)、[紧凑顶部](compact-chrome-results.json)、[浏览器](device-results.json)、[界面](ui-visual-results.json)、[构建日志](build.log)。

## 原签名与公网下载

[公网发布流程](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38125813188)通过，自动更新源同步到同一原签名安装包。

[下载正式 1.5.16 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.16-gecko/PocketChat-1.5.16-gecko-arm64.apk)，支持覆盖原签名版本。

- 版本：1.5.16 / code 42；大小：120470769 字节。
- SHA-256：`06f5d194776f856a5087bb33131513e60ddf3c6e724fe86d8fc38b766569f0d7`。
- 原证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。
- [APK 校验](apk-verification.json)：非调试、排除测试组件、16 KB ZIP 对齐。
- [匿名完整下载](public-download-verification.json)与[自动更新源](public-update-feed-verification.json)确认版本、源码、哈希和原证书一致。

## 验证边界

Android 15 x86_64 模拟器中执行真实生产代码、Gecko 浏览器、服务和 Mihomo；受控账号/网站与代理提供可重复检查，没有连接用户真机或真实 ChatGPT / Google 账号。探测值不代表 ChatGPT 生成耗时；内置完整线路与外部连接响应计时不宜直接比较。探测站点不可达时明确显示失败，不承诺任意网络必有毫秒值。

普通提醒仅保留回复完成。Android 前台服务必须保留系统提示，此版本将其设为静默；系统可能提升至 LOW 或继续显示条目，不能承诺通知抽屉完全隐藏。系统保活与环境隔离继续保留。
