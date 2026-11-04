# 会话界面专项验证

基线是前一轮本地提交 `1e3086a8e38ce736a9ae7acaaf54aeb40ca71e49`。对应[实际改动说明](../../docs/CHAT-FLUIDITY-v2.0.47-candidate2.md)。本目录的 JSON、原始 TAP 和编译诊断均已保存；`manifest.json` 绑定本轮八个生产文件与证据文件的 SHA-256。

| 验证 | 结果及范围 |
| --- | --- |
| 网页控件观察 | 基线 76、当前 80 项通过；直接执行完整生产脚本，比较控件、回复、错误及资源观察结果。 |
| 网络与顶部工具栏 | 当前 38、基线 16 项在两种 JSON 实现下通过；既有状态及紧凑工具栏回归各 88、44 项通过。 |
| 加载提示 | 前后共 95 项通过，包含二十秒阈值、错误详情、横竖屏、无障碍文字与淡出回调竞争。 |
| 会话帧路由 | 21 项通过，验证混合通知合并、立即同步模型引用及暂停恢复。只有真实会话通知绑定状态消息，纯展示事件不重复弹出提示。 |
| 下载卡片与焦点 | 卡片 96 项在两种 JSON 实现下通过；焦点、返回、键盘及布局 103 项通过。卡片单独测试中的展示请求适配器直接执行，真实帧合并由上一项单独检查。 |
| 网页与重新加载恢复 | 原有 105 项及重新加载 131 项通过，未放宽原有恢复、输入与任务身份断言。 |
| 相关网页观察回归 | 回复观察 37、绑定及加载 125、交互调度 44 项通过；资源观察直接执行 17/17 通过。 |
| 原生 API 联合编译 | 38 个完整生产 Java 文件通过真实 Android SDK 37.1 API 编译；周边应用接口由源码生成明确的编译边界，未替代 Gecko SDK。 |

网页工作量先预热观察器，再运行 600 个带标签历史控件、40 次流式更新及观察。减少的是整页按钮查询和标签读取；无标签控件的文字回退保持实时。网络测试的 Handler 与帧队列由适配器分别推进；加载、卡片及帧测试统计实际提取方法的控件写入和回调。这些计数不等于 Android 帧耗时、手机卡顿率或真实网站性能。

原有资源观察 Python 封装在当前 Node 24 上用 `node --test` 启动非标准测试文件名，只取得文件级 1 项，未满足其要求的 17 项门禁，失败记录保留为 `resource-wrapper-node24.json`。未修改或放宽该门禁；使用 `node --test-reporter=tap tests/resource-web-observer.cjs` 直接执行了全部原有 17 项，原始输出和严格 17/17 汇总分别在 `resource-observer.tap`、`resource-observer.json`。

主要复跑命令（路径按本机安装调整，基线提交须在本地 Git 中）：

```sh
python3 tests/ux-shell-host/frame_binding_run.py --java-home /path/to/jdk17 --output work/chat-frame.json
python3 tests/loading-performance-host/run.py --java-home /path/to/jdk17 --output work/chat-loading.json
python3 tests/chat-chrome-performance-host/run.py --java-home /path/to/jdk17 --json-jar /path/to/json.jar --output work/chat-chrome.json
JSDOM_MODULE=/path/to/node_modules/jsdom python3 tests/browser-controls-performance-host/run.py
python3 tests/ux-native-compile/run.py --java-home /path/to/jdk17 --android-jar /path/to/android-37.1/android.jar --output work/chat-native
```

未生成本轮 APK，也没有新代码的 Android/Gecko 设备执行、真实账号或帧率验收。编译记录中的基线提交及工作树标志如实保留，最终执行源码由逐文件哈希绑定。
