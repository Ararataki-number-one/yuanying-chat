# v1.6 入口与出口订阅实施说明

本文件说明当前补丁的代码行为和合并接口。代码基于 v1.5.21-gecko。它不是上线或 ARM 真机测试通过的声明。

## 已实现的行为

- 入口来源继续保留现有 URL、原生 Mihomo 解析和环境选择，不改变已有订阅凭据或登录目录。
- 出口来源有独立的加密来源列表、来源代次、版本、最后有效快照和更新状态。
- “入口订阅”和“出口订阅”分开显示；出口页同时列出订阅节点和原有手工 SOCKS5 出口。
- 出口刷新只修改候选库，不写环境的实际网络设置，不启动或重载代理、不轮换固定出口。
- 当前选中出口被删除、替换或改密时，已有环境仍保留自己的原配置。下次保存应用必须选择当前可用节点并通过校验。
- 名称只用于显示；同名不同服务器不会合并，同端点不同密钥不会静默覆盖成多个身份。
- 更新失败保留最后有效快照；旧请求失败不能覆盖更新成功后的状态。
- 使用中或待应用设置引用的来源不能删除。未使用来源删除留下墓碑，迟到响应不能复活来源；重新添加产生新代次。
- 加密库解密失败、内容损坏或版本较新时，库进入只读状态。修改失败保留原密文，当前环境可继续使用自己的既有配置。

## 明确支持的导入范围

第一阶段只支持 TCP SOCKS5 出口，最多 1 MiB、256 个节点、8192 行。

### YAML 的 proxies 节点列表

```yaml
proxies:
  - name: "Tokyo fixed"
    type: socks5
    server: proxy.example.invalid
    port: 1080
    username: "fixture-user"
    password: "fixture-password"
    udp: false
    region: "Japan"
    x-pocket-id: "provider-stable-id-01"
```

也支持每个节点位于单行的流式映射：

```yaml
proxies:
  - {name: "Tokyo fixed", type: socks5, server: proxy.example.invalid, port: 1080}
```

支持单引号、有限的双引号转义（引号、斜杠、反斜杠）、注释、带 UTF-8 BOM 的文本和缩进一致的平面字段。`region`、`x-pocket-id` 是可选扩展字段。`udp` 可为 true/false，但本应用的固定出口仍仅使用 TCP；`tls` 仅允许 false。

这不是通用 YAML 解释器。完整 Clash 配置的 rules/proxy-groups/dns、VLESS/TUIC/SS 等混合协议、YAML 标签/锚点/别名/合并键、嵌套字段、多行标量、未知字段、重复字段、重复节点身份，以及未支持的转义都会拒绝整次刷新并保留旧快照。文本字段为 null/布尔/数字等 YAML 特殊值时，必须加引号，避免把不同类型误当凭据。供应商应输出 SOCKS5 的 proxies-only 列表。

### 每行一个 SOCKS5 URI

```text
socks5://fixture-user:fixture-password@proxy.example.invalid:1080#Tokyo%20fixed
socks5://[2001:db8::1]:1080#IPv6
```

账号、密码和名称使用 UTF-8 百分号编码，`+` 保持加号。URI 不能带查询参数或非空路径（单独 `/` 除外）。不支持任意 base64 凭据扩展和 UDP/TLS URI 开关。

## 身份、版本和活动线路

出口来源：`exit-source-<hash>`，与入口来源 `entry-source-<legacy-url-hash>` 分属不同命名空间。来源 URL、凭据、节点快照和原始缓存只写 SecretStore 加密文件，不输出日志、不展示完整地址。

出口节点：`exit-node-<hash(sourceId, nodeKey)>`。`nodeKey` 优先使用 `x-pocket-id`，否则使用规范化服务器、端口和用户名；名称和密码不参与节点身份。更改密码保留 nodeId，并改变 `credentialRevision`、`configRevision`。没有供应商稳定 ID 时，端点或用户名变化产生新节点，旧节点变为不可选。

现有 `NetworkCatalog.exitId(config)` 仍是 host/port/user/password 的旧线路指纹，用于保留既有固定 IP 基线。它不是新的来源/节点 ID。运行连接与浏览器/预认证池应使用已应用的来源/节点/配置修订号区分线路代次，不能因候选库刷新而修改。

`NetworkDraft.candidate` 新增以下加密设置键：

| 字段 | 意义 |
|---|---|
| entrySourceId | 类型化入口来源 ID |
| entryNodeId | 当前原生入口选择器名称与来源组合的 ID；空表示待优选 |
| entryConfigRevision | 整份真实入口 provider 快照的摘要 |
| exitSourceId | 出口来源 ID；手工出口为空 |
| exitNodeId | 稳定的出口候选 ID；手工出口沿用旧 ID |
| exitConfigRevision | 实际端点和凭据的修订号 |
| exitCredentialRevision | 用户名与密码的修订号 |

入口 nodeId 仍对应现有 Mihomo 名称选择器；本补丁不宣称已从所有入口协议提取稳定端点身份。入口整份 provider 修订号可拒绝同名节点配置更新后的旧候选。

## 应用事务

`NetworkCatalog.validateAndRun(candidate, currentCatalog -> write)` 使用进程内锁和原有跨进程 network-catalog.lock。它重新读取加密库，检查入口快照以及出口来源/节点/配置/凭据修订号，再执行写入。来源刷新/删除使用相同锁。

NetworkUiProvider 在保存 pending-network 时验证一次；忙碌任务完成后、写入活动设置之前再验证一次。活动写入事务从 currentCatalog 读取当时的 provider 字节，避免编辑期间更新导致旧字节与新元信息混用。

`EnvironmentSpecRuntime.desireNetwork` 在 pending-network 已保存后、释放网络库锁后调用，避免网络库与环境仓库锁次序相反。环境记录失败保留 pending 设置并返回明确的非致命提示；已有实际线路不回退。后续空闲重试重新检查来源修订号。

## 缓存提交与进程中断

出口缓存使用来源、快照修订号和内容摘要构成的独立加密槽。槽名编码为 a–p，满足 SecretStore 的 `[a-z-]+` 要求。

先写新快照，再通过 SecretStore 的 AtomicFile 提交库中 cacheKey/cacheDigest 指针；库提交完成后才删除上一快照。提交前进程终止，旧库仍引用旧有效缓存；提交后进程终止，新库引用新有效缓存。读取额外核对摘要。

提交前突然终止可能留下未引用的加密文件，不会误认为活动快照。本补丁未提供孤立文件自动清扫；后续可在严格排除当前指针且持有同一锁的情况下加入清扫。

## 验证

已经在主机运行：

```bash
python3 tests/exit-subscriptions/run.py
```

需要 javac/java 在 PATH。当前结果为 54 项 parser/identity 检查通过，覆盖稳定身份、改密修订、同名节点、缓存槽字符限制、编码、URI、YAML 拒绝分支和大小/节点上限。它不证明 Android 加密、真实代理、网页登录或网络时延。

新增 `tests/gecko/ExitSubscriptionCatalogTestActivity.java`，用于独立 `.test` 应用的真实 Android SecretStore 回归：来源命名空间、加密缓存、固定环境设置不变、旧凭据候选拒绝、失败快照保留、在用与 pending 引用删除保护、墓碑/再添加代次、旧入口快照拒绝，以及损坏/未来/小数版本/尾随内容的只读密文保护。输出 exit-subscription-catalog-results.json，不输出凭据。该 Activity 必须在 integration 测试清单中注册并在设备运行；当前未声称已执行。

仍需实际 ARM 手机验证：两类来源真实更新、固定 IP 校验、回复期间延后应用、代理进程重启、网络切换、原网页登录及前后台恢复。来源下载优先使用当前已验证的应用代理；没有就绪内部线路时，来源下载采用与现有入口订阅相同的 HTTPS bootstrap。来源下载失败不会切换 ChatGPT 网页线路，也不会给网页直连回退。

## 文件和合并接口

- NetworkCatalog.java：加密双来源、身份与快照、墓碑、只读保护、事务。
- ExitSubscriptionParser.java：无 Android/JSON 依赖的边界明确解析器。
- ExitSubscriptionIdentity.java：类型化 ID 和安全缓存槽。
- ExitSubscriptionFetcher.java：HTTPS 获取，禁止重定向，限时限大小。
- NetworkDraft.java：候选选择和修订字段。
- NetworkWorkspaceUi.java：入口/出口分区、更新、来源详情和安全删除。
- NetworkUiProvider.java：保存与应用时重复验证，环境 desired 配置同步。
- tests/exit-subscriptions/：可直接运行的主机测试。
- tests/gecko/ExitSubscriptionCatalogTestActivity.java：需要设备运行的加密库回归。

不增加整机 VPN、自动出口轮换、浏览器引擎或 ChatGPT 原网页以外的聊天实现。
