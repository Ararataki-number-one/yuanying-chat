# 2.0.23：外部 VPN 路由覆盖准入

versionCode 76，基于已发布的 2.0.22，包含上一轮已完成的网络保护最小补丁。

- 外部网络未设置显式代理且要求 VPN 时，新的网页与 Worker 请求需确认当前 VPN 的 IPv4、IPv6 默认单播路由。缺少路由、存在排除路由、接口不一致或当前网络变化时，保守阻止新请求。
- 无法确认覆盖时说明原因，提供检查 VPN、使用应用内线路或显式代理的方向。不会自动降级保护或重发聊天。内置固定出口与显式代理沿用原逻辑。

兼容收紧：Android 8–12L 无法通过当前公开 API 确认完整路由，受保护外部 VPN 模式将拒绝新请求；仅 IPv4 且阻断 IPv6、以及使用 /1 分割默认路由的配置也可能被保守拒绝。这不表示这些配置已经泄漏。

同组受控 Android／Gecko 对照已确认分流遗漏目标的新请求准入缺口被关闭。该结论不代表整体防泄漏或手机验收；已获准的在途请求、真实切网、完整 DNS、公网 IPv6、Shared Worker 与 Service Worker 仍有未验证边界。新增路由检查的手机耗时和功耗未测。

详见[网络保护专项记录](https://github.com/Ararataki-number-one/yuanying-chat/blob/v2.0.23-gecko/docs/NETWORK-PROTECTION-20261027.md)；前版修复见[体验修复记录](https://github.com/Ararataki-number-one/yuanying-chat/blob/2915e250bc24a94aab409430d059efdb190e2493/docs/EXPERIENCE-RELIABILITY-20261026.md)。

本次同源码的必需受控 Android 发布检查已通过。
