# 浏览器维护验证记录

日期：2026-11-11。此记录对应暂停新功能后的导航修复与维护整理，配套说明见 [MAINTENANCE-AUDIT.md](MAINTENANCE-AUDIT.md)。

## 结果与源码归属

本轮统一入口的 **18 / 18 组通过**，运行时间为 **284.728 秒**，UTC 16:23:43 至 16:28:28。执行器记录的 **409 个生产与宿主输入文件**、依赖文件和运行时 HEAD 在执行前后未变，`changedInputs` 为空。另在同一冻结源码窗口执行了资源恢复的 3 个现有故障变体：均成功编译并执行，在各自指定行为断言被拒绝。

正式基准仍是 `v2.1.4-gecko`、versionCode `106`，基准提交 `7383bb1dd82c5d2155ba7c8dcc11b541478f6cfe`。本次执行发生在维护变更提交之前，结果中的 `sourceCommit` 为当时工作树的父提交 `815f7feeeb73de64d1edd3d0348c204bf7a2d249`；**409 个逐文件 SHA-256 才绑定本次实际执行的工作树内容**，不能把父提交本身当作已包含本轮修改。

最终证据目录：

`/workspace/scratch/d82e7decf2fd/maintenance-validation/final-after-connection-fix`

| 回执 | SHA-256 |
| --- | --- |
| `results.json`，18 组主结果、命令、日志哈希、源码与依赖哈希 | `1a3f9b24fca85a5707d4c0a3a02420b7a7ee5052ad7216949b8649530a241497` |
| `native-compile/receipt.json`，完整列出的 Java 源码与编译边界 | `3a30e9c81c69c24c56cae6e8047f23276b685370f3c1b62c2dfa191333c0bec4` |
| `resource-recovery-controls.json`，3 个故障变体、预期失败及日志哈希 | `8ef2ead2af1574b8319841a77c3b9ff6a1454a1196ab2fd6dcc275688f520027` |

目录中的 `page-recovery.log` 保存页面恢复与嵌套重载的完整 JSON；`address-ui.log` 保存两项地址界面执行结果。各组日志的 SHA-256 均记录于主结果。早先 `accepted/results.json` 的 16 组通过是连接竞争修复之前的检查点；`final/results.json` 是更早的失败记录，均不作为本次通过依据。完整临时日志未加入仓库。

## 各组实际结果

所有正向行为检查均通过。表中的故障变体是编译后运行并触发指定断言的负控，不把编译失败或缺少依赖视为成功。执行器之间存在复用，因此不把各行相加声称独立用例总量或产品覆盖率。

| 执行组 | 本次结果 | 主要验证边界 |
| --- | --- | --- |
| address-policy | 185 项 | 实际地址解析、公共 URL 与输入策略 |
| session-navigation | 171 项；24 个故障变体 | 实际 `ChatSession` 导航、连接恢复、Stop、历史、最新用户目标及独立任务归属 |
| driver-ownership | 280 项；5 个故障变体 | 当前 Gecko 导航方法、原生页面身份与迟到回调 |
| resource-client | 49 项；7 个故障变体 | 页面完成、HTTP 错误与快照等待阶段的事件隔离 |
| addon-lifecycle | 51 项；13 个主要故障变体 | 当前 addon 生命周期与旧加载回调隔离；保留既有冷启动边界检查 |
| ip-transport | 410 项 | 当前 IP 传输协调逻辑与受控回调；无真实 IP 查询 |
| resource-recovery | 40 项；另有同源码 3 个故障变体回执 | 异步 CPU/TLS 准备、资源重试、页面归属与原 60 秒绝对期限 |
| page-lifecycle | 44 项 | 完整当前 `PageMemory` 与 `WebReplyObserver` 类，在受控调度与存储边界运行 |
| draft-policy | 89 项；4 个故障变体 | 本地草稿、页面/路由隔离及相应生产类 |
| chromium-navigation | 276 项；8 个故障变体 | 当前 `BrowserActivity` 方法、选择器/权限取消重入及独立传输边界 |
| page-recovery | 161 项；7 个故障变体；嵌套重载 131 项 | 原恢复/清理断言、Gecko 生命周期调用归属、关闭所有网站与重载确认 |
| persistent-profile | 两次各 11 项；5 个故障变体 | 当前 CPU/TLS 与 `GeckoRuntime.create` 实际路径消费者、原持久化目录 |
| profile-maintenance | 3 项 Python 测试 | 其余原始 pin 不变、无关 Gecko 方法变化不破坏行为门禁、未知依赖被拒绝 |
| environment-entry | 32 项 | 当前环境入口的身份与已有文档保留 |
| address-ui | 展示/提交 68 项及 8 个变体；布局 210 项及 4 个变体 | 实际地址显示、提交与测量/布局方法；字体和 View 为声明的 JVM 边界 |
| bridge-ownership | 18 项 | 生产桥接请求生命周期 |
| browser-runtime | 60 项 | 当前运行策略、恢复、环境隔离与持久化路径行为 |
| native-compile | 67 个完整生产 Java 文件共同编译通过 | 实际 Android API 和依赖；262 个仅供编译的应用边界文件 |

连接竞争的回归覆盖了：B 尚在等待页面快照或网络时，旧连接完成不能重新加载 A；显式目标 B 优先于旧页面或旧任务的地址；没有显式用户选择时，保留原有任务恢复顺序。Stop、连接失效后重试、同步回调内再次导航及历史导航都有对应正向场景与反例。

关闭所有网站的回归执行实际 `closeWebsitePages`、`closePopup`，覆盖多弹窗和同步重入；最终回主页调用在宿主中是明确声明的调用方边界。检查验证清理不会插入返回父页的旧导航，也不会使最终回主页操作覆盖一个较新的用户导航。

资源恢复保留原 34 项行为，新增 6 项页面归属与同页 ChatGPT 任务恢复检查。原设备 fixture 的 42 个 `resourceCheck` 调用及 60 秒绝对期限未改。旧 fixture 将 localhost 恢复与 ChatGPT 网页任务混用的记录已改成明确的合成独立资源任务；同页网页任务另按实际 origin/route 匹配验证，跨页网页归档由完整 observer 的生命周期执行器覆盖。

## 可复现入口

```sh
python3 tools/browser/check_maintenance.py \
  --java-home /path/to/temurin-17.0.21+9 \
  --json-jar /path/to/json-20250517.jar \
  --android-jar /path/to/android-api-37.1/android.jar \
  --webkit-jar /path/to/webkit-1.14.0/classes.jar \
  --snakeyaml-jar /path/to/snakeyaml-2.3.jar \
  --output work/browser-maintenance
```

本次确切的绝对路径、逐组命令、退出码与耗时见主回执。省略三个原生编译依赖参数时，入口执行 17 个宿主组；本报告使用了全部参数。入口不下载依赖、不生成历史源码投影、不修改版本或发布设置。

资源恢复的 3 个现有反例可通过 `tests/resource-recovery-host/run.py --mutation` 分别选择 `sync-runtime-only`、`pretend-allocation-ready`、`obsolete-navigation-owner`，其余依赖参数与正常宿主一致。它们必须非零退出、准确命中预期 Java 行为断言，且不得生成正向通过报告。此次只使用下面列出的 JSON 实现，没有声称双 JSON 全套通过。

## 依赖与编译范围

| 依赖 | 本次实际版本 / SHA-256 |
| --- | --- |
| 编译器 | Temurin JDK `17.0.21+9`，`javac 17.0.21`；官方压缩包 SHA-256 `8b9b611d917e3dfd8419d3566b5949226f69b052fed7e109c1368add1dfe8711` |
| JVM JSON | `json-20250517.jar`：`3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796` |
| Android API | 实际平台 `37.1`，revision `1`；`android.jar`：`d827b4304f0144ad6332f7a236ccf0659f6bd845f5ba739db475d9e822272c85` |
| AndroidX WebKit | `1.14.0` AAR 内的真实 `classes.jar`：`7ab072324a84b56a23fdbf31040adb6d0f97c64fb5ad0965ff7834849ffea5ce` |
| SnakeYAML | `2.3`：`63a76fe66b652360bd4c2c107e6f0258daa7d4bb492008ba8c26fcd230ff9146` |

67 个完整文件的清单保持在 [production-sources.json](../tests/ux-native-compile/production-sources.json)。其中包含本轮修改的完整 `BrowserActivity`、`GeckoAddressUi`、`MainActivity`；其他应用依赖由当前源码生成只用于编译且方法体抛异常的边界。`R` 标识符也是明确的编译边界。该检查没有提供或编译完整 Gecko SDK，没有执行这些边界。

`ChatSession` 与 `GeckoWebView` 的相关当前方法由各行为宿主编译执行，完整 `PageMemory` 与 `WebReplyObserver` 则由页面生命周期宿主编译执行。宿主中的 Android、Gecko、系统 WebView、网络、调度和存储替身均在各自报告中声明；API 编译通过也不等于这些系统的实际运行通过。

持久化路径检查只取消了 GeckoWebView 无关整文件历史形状的约束，改为当前源码消费者提取、输入来源与执行前后不变性检查；保留其他 13 个原始 pin、原有两次各 11 项路径断言及 5 个错误路径变体。新增“无关方法变化仍通过”的回归，没有继续增加历史投影适配层。其他历史窗口证明与全量源码投影回归仍是单独的检查范围。

## 七个修改生产文件的输入指纹

以下值直接取自主回执，路径前缀均为 `app/src/main/java/local/pocketchat/`。提交时应将待提交文件与这些值逐一核对。

| 文件 | 本轮 SHA-256 |
| --- | --- |
| `BrowserActivity.java` | `9521b945a2d3ac1b196db2687f8e8d471f0247b7d1ea28644c0a7c6f8548e333` |
| `ChatSession.java` | `8ae161ce14a8ce7b6c2cf262b7173240e83a2e5c59f0ebe60dd8cd5f83536c42` |
| `GeckoAddressUi.java` | `a8a31285a52b51f6c5f3e8549e2d43af0ef23f83b8d636f07dbff623e947244d` |
| `GeckoWebView.java` | `8f6f149ba2b6d8f1ec86aed7fb591b92650331830ce911af7c3f13062cf5a6a5` |
| `MainActivity.java` | `67de3d2f9c6ab6e016342bac18c9b1095aa39bda9610796fe89495a2a7cdc9a0` |
| `PageMemory.java` | `238e71855a493644c1a76d4f522f9620e9201c745f8bafaccac2d93012ffba19` |
| `WebReplyObserver.java` | `3b2decf1c7a9aae348251ff3afaca8e6d078907f25744fede6ba05c6ca1d6d92` |

## 未覆盖的验收

本报告对应当前源码的受控行为回归与指定原生 Java 的 API 编译，主回执明确记录 `actualAndroidExecution: false`、`fullAppBuild: false`、`fullReleaseQualification: false`。本轮没有据此证明真实网站连通、IP 归属、下载/上传成功、Android 字体与触摸表现、玻璃视觉效果或 Gecko/Chromium 真机运行。

完整 APK 打包、安装、签名、升级、Android API 32/35 设备门禁及全量历史源码回归不在这 18 组通过结论内；既往这些检查的失败也没有由本报告消除。若后续 CI 或设备验收运行，应另按该提交与实际结果记录，不回写成本次宿主执行已经证明的内容。
