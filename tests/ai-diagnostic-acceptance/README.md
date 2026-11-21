# 一条命令复核阶段二候选

提供**现存** JDK 17 和 Android JSON 兼容 JAR；脚本不下载依赖、不读取实际供应商凭据、不调用供应商。

```sh
python3 -B tests/ai-diagnostic-acceptance/run.py \
  --java-home /path/to/jdk17 \
  --json-jar /path/to/android-compatible-json.jar \
  --output-dir /path/to/new-acceptance-results
```

输出目录必须尚不存在，避免覆盖已有证据。各阶段日志、Java 当次生成的匿名 wire、两供应商的请求/回复合成样本和 `report.json` 均落在此目录。失败阶段会记录错误并继续独立阶段；依赖失败则明确标为 blocked。通过只代表已选宿主验收范围，不代表 APK、真机、Gecko 内核、设备线路或付费供应商验收。

## 清楚分开的阶段

1. `python-offline`：明确运行既有五个模块 `test_diagnostic_gateway`、`test_responses_diagnosis`、`test_responses_transport`、`test_responses_ledger`、`test_provider_gateway`，不把新 TLS 用例混入离线计数。
2. `java-evidence`、`java-route`、`java-http-parser`、`java-fresh-id`：真实生产 Java 类或成员配合 JVM 边界替身；证据阶段重新生成本次匿名快照。
3. `java-native-tls-callback`、`java-tls-state`、`java-tls-update-cause`：TLS 回调归属、期望状态和 AppUpdates 夹具生命周期检查；最后一项覆盖 14 个 direct 与 42 个 nested 控制。这些阶段没有真实 TLS 握手，也不推断真实 Android 进程退出原因。
4. `page-bridge`、`window-selection`：当前实现的生命周期和标签归属。默认 `--history current`，两个依赖旧 Git 对象的历史反例列为未选，不计作通过。
5. `http-cross-wire`：两家供应商的 **HTTPS 连接是内存替身**；请求通过真实 `127.0.0.1` HTTP 网关、真实临时 SQLite、生产 Responses 契约，再将确切 wire 交给 Android 的 Java 解析器。验证原始匿名编号、供应商路径/格式差异、重复请求只执行一次，以及 reasoning 不进入设备回复。
6. `https-loopback`：独立的**本机真实 TLS**阶段，使用临时合成证书、测试 CA 和固定环回地址；不连接真实供应商，也不改变生产证书验证。

跨层夹具为执行生产组合而设置的 admission 标志只适用于注入的内存供应商替身，不表示任何真实设备/部署验收通过。默认生产付费路径与部署配置不被修改。

## 历史与扩展宿主检查

执行历史证明需要已有本地 Git 对象。可以显式指定另一份本地对象库，脚本不会 fetch：

```sh
python3 -B tests/ai-diagnostic-acceptance/run.py \
  --java-home /path/to/jdk17 --json-jar /path/to/android-compatible-json.jar \
  --output-dir /path/to/new-full-results \
  --history full --history-object-dir /path/to/existing/.git/objects \
  --extended-jvm
```

`--history full` 会运行两个原始历史反例；缺对象或断言失败均使验收失败。`--history-object-dir` 只提供 Git 原对象，不替换工作树源码。`--extended-jvm` 额外运行 Gecko addon 和 UI 退出生命周期宿主检查。

脚本为子进程构造最小环境，不继承 API 密钥、代理变量或 Python 启动钩子；因此使用上述参数传入历史对象，而非依赖外层环境变量。Python 离线/HTTP worker 限制 socket 为数值回环，并将被阻止的非回环尝试视为失败；这是测试防护，不是整个操作系统或 JVM 的防火墙证明。真实 TLS 测试自行固定环回范围。
