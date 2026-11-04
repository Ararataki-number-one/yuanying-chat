# 十轮流畅性优化：最终验证

基线：`5900426428e00a95acf5126f6154f34ff2d46930`，2.0.47 候选2。完整改动清单见 [十轮流畅性优化](../../docs/PERFORMANCE-TEN-ROUNDS-v2.0.47-candidate2.md)。

- 统一回归的 28 个验证流程全部通过，JSON 相关新增流程分别使用桌面和 Android 兼容实现。
- 36 个完整生产 Java 文件通过真实 Android SDK 37.1 API 联合编译；应用边界由当前源码生成，明确只供编译，不执行或打包替身，没有提供替代 Gecko SDK。
- 检查结果所记录的当前生产文件哈希均已与最终源码复核。报告中的 `sourceCommit` 为修改前基线，`dirtySource`／`sourceDirty` 如实标记执行时工作树；源码身份另由文件 SHA-256 绑定。
- 环境异步读取错误提示的最终修正后，环境展示流程已针对最新源码重跑；本目录保存的是重跑后的结果。

`summary.json` 记录全部执行命令及生产源码哈希。`native-compile--receipt.json` 记录完整文件集合、编译器及 Android API 哈希。其他 JSON 提供对应固定工作量和边界测试；`manifest.json` 记录证据文件哈希。

性能数字统计实际执行源码中的读取、扫描、绑定与控件赋值次数。下载列表对照样本是本次功能增强完成、性能改动之前的检查点；聊天下载卡片和环境输入回调直接对照原始候选2。报告都标明适配器与数据规模，未将这些计数称为真实手机帧率或卡顿率。

完整 APK 未构建：所需官方 Gecko 输入域名被当前代理以 403 拒绝；准确 CI 输入包超过连接器下载上限。当前没有 Android 设备或 KVM。`build-status.json` 和 `profiling-feasibility.json` 保存实际边界；Gradle 清单生成及扩展版本检查通过，日志在 `gradle-config.json`。没有发布安装包或覆盖已有 Release。

可复跑入口：

```bash
python3 tests/run_ux_ten_rounds.py \
  --java-home /path/to/jdk17 \
  --json-jar /path/to/json-20240303.jar \
  --android-json-jar /path/to/android-json.jar \
  --android-jar /path/to/android-37.1/android.jar
```
