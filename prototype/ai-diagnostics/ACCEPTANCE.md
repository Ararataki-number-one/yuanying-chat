# PocketChat AI 诊断测试包验收

诊断候选基于 2.1.15 维护提交 `2b1853c7822f143dca9170cc36e7c6d2a647bc57`。测试包 ID 为 `local.pocketchat.aidiagnostics`，构建任务为 `:app:assembleDiagnostics`。

## Android 打包

使用 JDK 17、Gradle 9.8.0、AGP 9.4.1、Android 37.1 平台和 Build Tools 37.0.0。Gradle 发行包校验值见 [Gradle 锁定配置](../../gradle/wrapper/gradle-wrapper.properties)。

构建复用基线预编译 Gecko SDK `local.pocketchat.sdk:geckoview-caret:157.0.20261005135250-pocket3` 的 Maven 仓库及 assets。AAR 校验值见 [固定 Gecko 输入](../../third-party/sdk/geckoview-157.0.1-editable-selection.json)。

候选专用 Actions 工作流只构建诊断变体，使用临时测试签名。它校验 APK 签名、包名、ABI、诊断通道与 SDK 回执，并以短期 Actions 工件提供测试 APK。

在已有授权、带上述锁定输入的构建机上，从候选根目录运行

```sh
/path/to/verified/gradle-9.8.0/bin/gradle --offline --no-daemon :app:assembleDiagnostics \
  -PcaretSdkRepository=/path/to/verified/caret-sdk/maven \
  -PcaretSdkAssets=/path/to/verified/caret-sdk/assets
```

使用现有诊断变体签名配置。产物应在 `app/build/outputs/apk/diagnostics/`，以实际输出为准。安装前用现有 `aapt2 dump badging` 确认包名和设备 ABI，用现有 `apksigner verify` 核对签名，再向专用测试设备安装对应 APK。

## 单条宿主验收命令

从本候选根目录运行。输出目录应为此前未使用的新目录。已有的本地 Git 对象用于复跑两项历史桥接反例。

```sh
python3 -B tests/ai-diagnostic-acceptance/run.py \
  --java-home /path/to/jdk17 \
  --json-jar /path/to/android-compatible-json.jar \
  --output-dir /path/to/new-acceptance-results \
  --history full --history-object-dir /path/to/local-history/.git/objects \
  --extended-jvm
```

输出 `report.json`、逐阶段日志及合成 wire 文件。其他机器可用相同锁定输入的路径，也可选当前源码范围。参数见 [验收 runner 说明](../../tests/ai-diagnostic-acceptance/README.md)。

## 证据分级

- JVM 运行的是生产 Java 的指定类和替换的 Android／Gecko 边界，能验收协议、取消状态与路由选择代码。
- 本机环回用两家供应商替身贯通第 2 版网关与 Android JVM 解析。本机 HTTPS 单独验证握手、证书链和主机名。合成证书的信任范围只在测试进程。
- 模拟器或真机验收需要实际安装 APK。只有设备上观察到、并由受控端点核对的 DNS、线路切换和出站路径才能记为设备结果。

## 付费启用边界

设备验收使用合成 HTTPS 网关。真实 GPT／DeepSeek 保持关闭。服务端可按同一请求编号跨重启去重，Android 仅在同一 Activity 内保存最后一次状态不确定的请求编号。重新保存网关、变更证据、Activity 重建或进程重启都可能获得新编号。沿用编号和新请求分别展示。新请求的确认会注明先前可能已送达、付费网关可能再次计费，用户须再次确认。当前未引入设备端持久重试票据。

启用真实调用的设备和服务端门槛见 [Responses 说明](RESPONSES.md)。

## 手机验收

使用专用测试环境、合成页面与仅供验收的网关令牌。将自有实验域名及设备已信任且主机名匹配的证书交给本机测试网关。下列命令在持有该证书的受控实验主机上执行，域名和文件位置换成实际已授权值。

```sh
python3 -B prototype/ai-diagnostics/acceptance_https_gateway.py \
  --endpoint https://relay.lab.example/v1/diagnose \
  --cert /path/to/approved/fullchain.pem \
  --key /path/to/approved/privkey.pem \
  --token-file /path/to/private/test-token \
  --port 8767 --response-delay-ms 1500
```

测试进程绑定 `127.0.0.1`。在已有实验入口将该精确域名和路径转给本机进程。由实验设施保留 Host 和配置正确的 SNI，继续校验上游 TLS。现有入口与反代只记录无内容计数和时间，避免保存诊断正文、请求编号或访问令牌。Android 使用常规系统证书验证。端点需要通过当前浏览器环境批准的线路可达。

1. 在测试设备上安装对应 ABI，确认包名为 `local.pocketchat.aidiagnostics`。进入无登录的实验环境，将自有合成页面设为测试主页，长按底部「网页工具」。
2. 在两个标签页制造可核对的原生观察，例如实验 DNS 负例和普通加载结束。选择标签页，核对匿名编号和预览白名单。未配置网关时也可查看本地证据。
3. 配置已授权 HTTPS 网关及本次测试令牌，分别用 GPT 和 DeepSeek 选项发送合成证据。核对「本机观察」和「远端建议（待核实）」引用的是预览里的同一 `Tn/En`。无故障快照只显示本地记录和无模型调用。
4. 在延时窗口中点停止等待、切换线路或关闭助手。记录设备上的提示与实验入口计数，区分开始写入、可能已收到、收到回复。在同一个 Activity 用相同设置和证据重试，应显示「沿用编号发送」。重建 Activity 或重启后若需要再发，核对新编号与「可能再次计费」提示。整个过程不应自动重发。
5. 在受控线路分别核对 DNS、实际出口和切线。常规系统证书不认可的实验端点应连接失败。把实际设备类型、ABI、包哈希、线路种类和通过／失败项记录在一起。合成诊断和本机证据没有覆盖 Android 或设备路由时，应分别标注。

测试网关返回第 2 版结构化合成建议，不加载付费客户端。详细字段和本机测试在 [测试网关说明](ACCEPTANCE_HTTPS.md)。
