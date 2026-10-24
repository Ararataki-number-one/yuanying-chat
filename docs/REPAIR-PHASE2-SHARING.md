# 第二批：网络分享修复 S01–S07

基于 `e551c09`，仅修改分享及其订阅候选存储、回归验证。本批不更改版本号、不发布，也不包含体验性能改善的测量结论。

## 已实现的行为

| 计划 | 实现与边界 |
| --- | --- |
| S01 | 订阅原生解析成功后，在同一工作线程中 compose 一次 YAML，仅构造各候选节点。候选与原始源字节 SHA-256、原生 `configFingerprint`、表示版本绑定，存入加密网络库的独立 sidecar；公开节点元数据不含账号字段。分享优先使用候选，最后仍执行实际内核指纹核对。 |
| S02 | 按原生具体字段类型转换字符串、整数、布尔值、列表、对象。YAML `on`、`NO` 保留为字符串；数字凭据按字符串字段转换。HTTP 代理 / WS 的字符串请求头和 HTTP 传输的字符串数组请求头分别校验。 |
| S03 | 字符串整数使用 Go 的 base-0 规则，例如 `'01000'` 为 512、`'0x1bb'` 为 443，`'08'` 拒绝。最终网络端口须在合法范围内；不依赖整数溢出或端口回绕。 |
| S04 | 只规范化已知类型字段的唯一大小写 / 下划线别名。冲突别名拒绝；任意请求头键原样保留；原生分发依赖的 `name`、`type`、`smux` 保持精确键名。SS 插件二次解析没有下划线替换，插件原始键值还参与指纹，因此保留原始类型。 |
| S05 | 按 Mihomo v1.19.31 源码维护协议、传输和插件字段表，涵盖所需 HY2、TUIC、HTTP、gRPC、SS 插件、VLESS XHTTP 参数及 HY2 仅端口范围。外部路由、文件、脚本依赖和未实现的协议字段继续拒绝。新增参数仍以最终实际内核指纹核对为准。 |
| S06 | 选择了计划允许的提前告知方案：节点“更多”面板提前显示 YAML 分享范围；已识别 URI / Base64 来源说明不能独立分享，不伪装成支持转换。旧元数据仍可尝试有界单节点提取。 |
| S07 | 分别报告入口 / 出口的读取、参数检查、内核解析、身份核对阶段，不显示含账号的原始解析异常。整条线路一端失败时，另一端只要独立通过原生核验即可单独分享。 |

## 生命周期与资源保护

- 订阅源与候选指针使用同一次原子网络库发布；刷新、同名替换、地址修改、删除和迟到回调均检查当前源代次。当前与前一代缓存受清理上限约束。
- 可选 sidecar 缺失、损坏、写入失败，或候选数量 / 展开预算不足时，都保留按需提取路径；预算不足与确定不支持分开记录，不隐藏有效尾部节点的分享入口。原始源和网络库写入失败仍如实失败。
- YAML 总字节 / 语法节点 / 别名 / 嵌套上限、选中节点展开 / 文本上限继续有效。全库候选最多 4096 个、16 MiB，并有累计展开预算。无关节点不能通过构造展开耗尽选中节点的独立提取预算；显式节点名不受无关继承名遍历预算耗尽影响。
- 分享只读取原线路：先在 active snapshot lease 内复制配置对应的源字节，释放 lease 后才查网络库。避免与保存流程的 `Catalog → active snapshot` 锁顺序形成 ABBA 死锁。
- 候选是待核验的连接配置，不是内核核验回执。发送前重解析并比较指纹仍是必经步骤。没有 ChatGPT 登录、Cookie、聊天、环境私有数据或其他节点配置进入分享包。

## 本地验证

以下数字来自实际执行生产方法 / 类的主机验证，不能替代 Android 运行或真实代理测试。

| 验证 | 结果 | 范围 |
| --- | --- | --- |
| 原有分享 codec | 87 项 | 两个 JSON 实现；原有 YAML / 字符转义 / 单节点边界保持 |
| 候选 / snapshot 链路 | 44 项 | 两个 JSON 实现；源 hash / 指纹 / 版本、独立节点、100 aliases、缓存预算、4097 个不同节点、尾部回退 |
| 生产分享 UI 方法 / 回调 | 24 项 | 两个 JSON 实现；完整 route / nodeMenu / selected / verifyPrepared 方法体、单端失败、迟到回调和真实双线程锁顺序；显式 Android / native 适配器 |
| 生产网络库 | 165 项 | 两个 JSON 实现；原子源 / sidecar 发布、保存失败、跨实例 / 独立 JVM 代次、缓存清理、本地导入、可选索引失败 |
| 数值完整缓存链路 | 260 项 | 两个 JSON 实现；生产 candidates → parsed / importLocalSources → shareCandidate → Bundle / provider；大整数、浮点边界和缓存写入失败回退，存储及原生身份为明确的主机适配器 |
| 关联来源 / lineage / intent | 100 / 26 / 85 项 | 主机生产路径，Android JSON |
| 分享 JSON 边界 | 55 项 | 两个 JSON 实现；精确整数与浮点类型、严格格式 / 资源限制、旧接收端版本拒绝与普通配置兼容 |
| 上游原生解析差分 | 49 / 49 | 生产导出前后实际运行 Mihomo v1.19.31 `-t`，逐例检查类型与原始字段保留；原 44 项及其基线记录保留，新增插件数值边界 |
| 浮点凭据原生字节对照 | 30 + 92 组 | 原 30 组边界及 46 个二进制指数边界的正负值；每组读取本机合成 SOCKS5 服务收到的原始 / 导出认证字节，无外部代理连接 |
| 最短表示固定样本对照 | 16,286 / 16,286 | 同一批二进制值，生产转换与 CPython 最短表示一致；作为跨实现诊断，原生语义另外用上述认证字节核对 |

原生差分调用的是未打 Pocket 补丁的 Linux core，**`-t` 只证明配置解析和构造接受，不证明 Pocket 指纹等价**。浮点凭据另外验证了本机合成 SOCKS5 认证字节，服务在认证阶段即拒绝，不连接目标站点。主机身份字符串是合成数据。没有进行用户真实代理链、外部账号认证、网络延迟、吞吐或真机体验测速。

本地证据保留在工作区 `work/network-sharing-native-matrix/final/results.json`、`work/network-sharing-host/`、`work/network-share-ui-flow/`、`work/network-catalog-host/` 和 `work/sharing-phase2/summary.json`。测试输入均为合成配置，无用户账号。

独立审查在 `d3d27f6` 上复现了两个额外边界：Android JSON 复制会损失大于 `Long.MAX_VALUE` 的 HY2 `uint64`，JDK 17 的浮点最短表示也会把 `1e23` 凭据导出成与原生不同的文本。修复仅将对应 `uint64` 字段的大值保留为原生支持的精确十进制字符串；浮点字符串按原生 `FormatFloat('E', -1, 64)` 的最短往返规则生成，浮点到整数按真实二进制值截断。后续独立审查又发现仅取最近十进制值会漏掉 2 的整数次幂两侧不对称的往返区间，已补同精度相邻候选，并按距离和偶数舍入选取；原四组失败认证字节与修复后的 92 组正负边界对照均保留。原始插件映射类型保持不变，最终原生指纹核验继续保留。修复前证据、修复后双 JSON / 原生对照保存在 `work/sharing-phase2/independent-review/`。

## 恢复开发后的数值补充修复

独立复核发现 SS 插件原始参数在 Android JSON 往返时仍会损失整数精度或浮点类型。已用真实 Mihomo 向本机合成 WebSocket 服务发送请求，确认 `9223372036854775808`、`18446744073709551615`、`1.0` 和 `-0.0` 的 Host 曾发生变化。分享专用 JSON 读写与复制现在保留原始数值，不改变普通设置的 JSON 行为；候选 sidecar 更新到版本 2，旧缓存按原始订阅回退，可选缓存编码超限仍不阻止来源保存。

普通配置继续使用分享格式版本 1。只有旧 Android 接收端不能无损处理的数值使用格式版本 2，并提示需要 2.0.17 或更新版本；旧接收端会明确拒绝该版本，新接收端仍读取版本 1。原生最终指纹检查、字段白名单和外部依赖限制保持不变。

累计展开预算也已修复：单节点因复杂度、循环或类型检查失败时，已消耗的访问仍计入来源累计预算；最后一项受剩余额度约束。耗尽后仅停止可选缓存构建，所选节点仍可使用独立预算按需提取。真实 Mihomo 接受的合成订阅及同输入修复前后回执、6 个追加回归均保留。

修复前后各 18 条本机原生请求回执已保留，修复后每组原始配置、缓存导出和分享往返的 Host 相同。该结果证明合成参数的线端语义保留，不代表真实线路测速或真机验证。两项新边界及后续累计预算修复的完整证据保存在工作区 `work/plan-repairs/resume-20261024/`。

## 复现入口

设置 `JAVA_HOME` 为 JDK 17、`JSON_JAR` 为 org.json 或 Android JSON JAR，`YAML_JAR` 为 SnakeYAML 2.3：

```sh
python3 tests/network-sharing-host/run.py --java-home "$JAVA_HOME" --json-jar "$JSON_JAR" --yaml-jar "$YAML_JAR"
python3 tests/network-catalog-host/run.py --java-home "$JAVA_HOME" --json-jar "$JSON_JAR"
python3 tests/network-source-host/run.py --java-home "$JAVA_HOME" --json-jar "$JSON_JAR"
python3 tests/network-lineage-host/run.py --java-home "$JAVA_HOME" --json-jar "$JSON_JAR"
python3 tests/environment-intent-host/run.py --java-home "$JAVA_HOME" --json-jar "$JSON_JAR"
python3 tests/network-sharing-host/native_matrix.py --java-home "$JAVA_HOME" --json-jar "$JSON_JAR" --yaml-jar "$YAML_JAR" --native-core "$MIHOMO_TEST_BINARY" --baseline e551c09
```

`network-sharing-host/run.py` 已接入现有 CI 入口，同时执行候选和完整分享回调回归。

## Android 尚待验收

`NetworkSharingIntegrationActivity` 保留原 19 个协议 / 类型样例并增加 12 个数值边界及 5 个插件数值边界，共 36 个实际 Pocket 指纹往返样例。读取 `sharing-schema-matrix.json`，执行原生原始解析 → 候选 → 真实网络库导入与加密 sidecar → 重新读取 → 导出 / 导入 → 原生导出解析 → 指纹比较；每例清理临时来源并检查活动网络快照字节未变。也保留实际点击“入口读取失败，仅分享出口”的检查。原有 100 aliases、无关 metadata、可运行本地固定出口线路等验证继续保留。

必须在整合后的 Android 构建中完成上述 fixture、既有网络分享 UI 和关联环境网络回归后，才能称本批 Android 验收通过。当前主机生产路径已编译执行，Android fixture 仍需完整 Android / Gecko 编译与运行。不得把 Linux `-t` 或主机适配器结果作为该验收的替代。
