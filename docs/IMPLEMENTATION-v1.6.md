# 1.6 网络与环境基础实现

版本：1.6.0 / code48，基于正式 v1.5.21，候选未发布。

## 已落地

- NativeNetwork 明确 BLOCKED、VERIFIED、DEGRADED_VERIFICATION。
  保留准确原线路回执时，恢复回调和发送前检查允许继续；主动出口核验
  仍准确返回未核验。首次/改变线路/固定 IP 不符不会放行。
- gstatic 失败时只通过已验证固定出口做有界 ChatGPT HEAD。HTTP403、
  429、5xx 表示传输可达，网页可用性另报。两次双方传输失败才恢复。
- NetworkStatusPolicy 把新目标响应与旧测速失败分开，网络详情显示
  线路准入与检测器状态；不上屏弹警告、不重发聊天内容。
- 入口和出口来源独立更新，出口首期为有明确边界的 SOCKS5 格式；
  手工出口保留。来源、节点、配置/凭据修订进入应用身份。
- schema7 为既有环境增稳定 UUID；EnvironmentSpec、Repository、
  ApplyCoordinator 分别管理期望配置、已应用配置和观测版本。

## 实施与回归

共享订阅库继续加密。刷新只更新库，不改变环境 active route；应用
候选重新核对库修订，过期时保留原路线并要求重新选择。环境文件使用
原 Keystore 及 AtomicFile，拒绝覆盖损坏或高版本数据。

既有预认证单用连接、8 秒期限、无网站预请求和连接池代次继续保留。
新增源/节点修订仅在应用时改变路线身份，订阅刷新不杀掉健康在途连接。

测试入口：NetworkHealthPolicyTest、NetworkStatusPolicyTest、
ExitSubscriptionParserTest、EnvironmentSpecTest；Android 新增迁移与
出口库测试，并扩展 NetworkOptimizationIntegrationActivity。

真正的指纹模板应用与网页自检在 1.7 接入。本版本持久化模型保持
applied=0，直到实际配置得到准确的运行时确认。
