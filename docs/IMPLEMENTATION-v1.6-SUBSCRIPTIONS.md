# v1.6 入口与出口订阅衔接

基线为正式 v1.5.23-gecko / 6a1bab77。双订阅、Mihomo 节点解析、来源刷新令牌、不可变加密缓存、独立环境实际快照、延后应用与取消/回滚已经由 1.5.23 提供；本候选保留这些实现，不引入旧候选的独立 SOCKS5 解析器。

入口与出口库分开，手工出口继续保留。刷新只更新候选库，不重载健康线路、不轮换固定出口。节点身份由实际连接配置计算，改名不能变成新的网络身份；来源或连接配置变化需要重新选择并验证。活动及 pending 快照不读取后来刷新出的其他字节。

## 本次复查修复

- 手工出口添加/编辑仅按当前端点与凭据指纹去重。历史别名仅供旧环境引用解析，编辑 A 为 B 后再次添加 A 必须创建独立记录，不能悄悄返回 B。
- 加密目录先校验版本、容器与行结构，再做支持的旧格式迁移。较新版本或损坏格式保持只读、保留原密文。
- pending 网络设置是保存意图的权威记录。新意图先暂存，释放网络库和活动快照锁以后更新模型，再确认可应用状态；模型失败或进程中断会精确恢复此前意图，不会让界面报告失败的候选随后自动应用。取消及启动恢复只对齐网络模型，保留最新浏览器配置；较新候选和不同环境身份不被旧回调覆盖。

## 环境绑定

入口使用 entrySubscriptionId、entrySubscriptionAddressRevision、entryNodeKey、entryPoolKeys/entryPoolNodeKeys。出口使用 exitSource；订阅出口使用 exitSubscriptionId/AddressRevision、exitNodeKey，手工出口使用 exitLibraryId 和实际端点指纹。

运行回执继续由 NativeNetwork.exitIdentity/transportFingerprint 与已冻结 provider 的 payloadHash/cacheGeneration 保护。订阅出口候选不要求存在旧 exitHost 字段。期望/已应用记录不包含凭据明文，也不把节点显示名称当连接身份。

## 验证边界

主机回归入口：tests/network-catalog-host/run.py、tests/network-source-host/run.py、tests/network-lineage-host/run.py、tests/sealed-file-host/run.py 以及 tools/gecko/run_profile_host_checks.py。设备回归继续使用新版 NetworkSources 与 NetworkSafeIdle 活动，新增环境迁移活动。

主机通过不代表 Android Keystore、实际代理、ARM 手机或网页登录通过。仍需真实来源、固定 IP、在途回复/文件操作、断网恢复与前后台验证。保留应用内代理边界，不增加整机 VPN、自动出口轮换或网页直连回退。
