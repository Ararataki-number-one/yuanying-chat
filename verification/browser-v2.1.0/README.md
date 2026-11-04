# 2.1.0 通用浏览器 · 本地验证

本目录保留提交前执行的真实源码验证记录，报告中的 `sourceCommit` 是运行当时的父提交，具体改动由生产文件 SHA-256 绑定。完整 APK 和 Android WebView 执行证据由 `Browser 2.1.0 and complete original Gecko acceptance` 工作流单独提供，不能由此目录的主机测试代替。

| 检查 | 范围 |
| --- | --- |
| 地址 185 项 | 真实地址策略，网址、搜索、公共 HTTP(S)、危险协议与地址规范化 |
| 启动偏好 50 项 × 两种 JSON | 实际偏好类与 Main 分发方法，保留原有任务入口 |
| 收藏/历史 36 项 × 两种 JSON | 实际生产库，容量、去重、损坏数据、标题上限与环境隔离 |
| 网站权限 43 项 | 实际控制器，HTTPS/origin/文档/前台身份与系统权限回包边界 |
| GET 下载 68 项 | 实际传输类，重定向、Cookie、路由、取消、长度与临时文件 |
| 文件流程 185 项 × 两种 JSON | 真实选择器方法、保存类、文件复制/发布/全局索引与安全回滚；Android 边界为适配器 |
| 路由与清理 | 19,459 项策略检查、400 项环境删除检查、54 项下载残留检查、11 项真实 Runtime 回执检查，另含 7,018 项线路保留检查和 48 项 × 两种 JSON 的真实方法边界检查 |
| 原生编译 | 59 个完整生产 Java 文件，真实 Android 37.1 API、AndroidX WebKit 1.14.0 与 SnakeYAML；无替代 Gecko SDK |

`host-results.json` 汇总同一批源码执行的 41 组新浏览器与此前会话回归，验证运行期间输入未变化。其中包含点击定位、下载布局观测、操作回执归属、围栏释放和双 JSON 实现下的持久化事件回执检查；这些主机测试不替代 Android 文件选择器及网络应用验收。`native-source-audit.json` 将当前 Java、编译输入和报告关联。`manifest.json` 校验本目录文件与此次生产源码。

复现前先恢复固定的本地历史基线，仅添加 Git 对象，不改 HEAD 或工作区：

```sh
python3 tools/browser/prepare_baselines.py
python3 tools/browser/run_host_checks.py \
  --java-home /path/to/jdk17 \
  --json-jar /path/to/json-20240303.jar \
  --android-json-jar /path/to/android-json.jar \
  --android-jar /path/to/android-37.1/android.jar \
  --webkit-jar /path/to/webkit-1.14.0-classes.jar \
  --jsdom-module /path/to/node_modules/jsdom \
  --output work/browser-host-controls
```

原生编译的周边应用边界仅用于检查签名、继承关系与 Android API，方法体不执行。主机测试不代表系统权限、摄像头、真实网站登录、SQLite/网络设备行为、APK 完整构建或手机帧率。真实 Android 工作流必须进一步验证同一 source/run/APK/SDK 的 Chromium 和 Gecko；2.1.0 的正式发布工具强制要求这份浏览器证据，并继续要求原签名。
