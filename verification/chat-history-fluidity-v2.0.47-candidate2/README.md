# 长会话与历史保存验证

基线：`f43adac5d746235f91edfeba50f495b84baa8acd`。

- `browser-order.json`：完整生产脚本，基线 41 项、当前 70 项检查，完整增量一致；1,200 条消息的 20 次流式更新在预热后顺序比较 47,960 → 0。
- `store-jvm.json`、`store-android-json.json`：两种 JSON 实现各 278 项前后版本合计检查。100 次变化快照的全文偏好写入 100 → 0、数据库适配器保存 100 → 100。
- `native-compile.json`、`native-compile.txt`：39 个完整生产 Java 文件与真实 Android 37.1 API 联合编译通过；235 个周边应用边界仅用于编译，方法体不执行。
- `source-audit.json`：生产源码、编译输入和执行报告哈希核对通过。报告中 work 路径指向原始运行位置，此目录保留相同内容。
- 其余报告覆盖回复观察、加载绑定、页面恢复和交互调度回归。

复现：

```sh
JSDOM_MODULE="$PWD/work/chat-smoothness-deps/node_modules/jsdom" python3 tests/browser-transcript-order-host/run.py
python3 tests/transcript-store-performance-host/run.py --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 --json-jar work/ux-build-deps/json-20240303.jar
python3 tests/transcript-store-performance-host/run.py --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 --json-jar work/ux-build-deps/android-json.jar --output work/ux-transcript-store-performance/android-results.json
```

DOM 使用 JSDOM 和明确的文字/几何适配。保存测试使用真实工作线程，Handler、数据库、偏好及 URI 边界为可控适配器；不是 Android/SQLite/SharedPreferences 设备执行。结果计数不代表手机 FPS、耗时或落盘字节数。本轮没有生成新 APK，也没有完成真实账号或手机验收。
