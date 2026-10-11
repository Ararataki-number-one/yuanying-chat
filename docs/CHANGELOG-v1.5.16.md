# 1.5.16 · 会话空间、实测延迟与完成提醒

- `NativeNetwork`、`NetworkRegion`、`RouteLatency`：补测恢复后的当前线路；限制频率及并发；外部响应检测遵循已有代理、VPN、连接世代与网络保护，禁用直连回退。
- `WindowNetworkState`、`NetworkUiProvider`、`NetworkWorkspaceUi`：传递真实延迟，区分未测、探测失败和历史读数；外部连接允许测速并正确说明测量含义。
- `DesignChrome`：缩小外层会话顶部，适应大字体，网络状态只读；保留环境切换与模式操作，保留官方网页及安全区。
- `QuietNotifications`、`ReplyNoticeLedger`、`ChatService`、`NetworkTransportService`、`AppPrefs`：迁移旧通知渠道，保活静默；普通提醒只在回复完成时发出，并按环境用索引数据库持久去重，删除环境同步清理记录。
- `EnvironmentEditorUi`：使用偏好按设置名称分组，移除提醒选项后不再依赖旧索引范围，避免进入环境编辑页时越界崩溃。
- Android 回归：增加当前线路自动补测、静默渠道、真实后台服务、稳定终态提醒、紧凑顶部、大字体与真实触控检查。生产包排除测试组件，继续使用原签名。

正式验证记录将在 `verification/compact-latency-notifications-v1.5.16/` 保存。Google 登录、真实 ChatGPT 账号与用户手机的长期运行不以受控测试代替。
