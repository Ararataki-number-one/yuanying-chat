# 2.0 实施包：官方 GeckoView 能力清单、资源保护与原生增强门槛

此实施包承接 1.6 的环境和网络数据模型、1.7 的模板与生效自检。当前可合并的代码继续使用官方 GeckoView，不包含自编译内核、不宣称已实现独立时区、Canvas、WebGL、音频或字体伪装。

## 已实现

### 可追溯的原生能力清单

`NativeCapabilityManifest` 与 `third-party/sdk/identity-capabilities.json` 绑定实际 SDK 坐标、上游 revision 和 AAR SHA-256。五项深层原生能力均为 `UNSUPPORTED`；`requireSupported` 拒绝所有当前没有实现的自定义原生控制。标准语言、显示和原生隐私保护由 1.7 的 Gecko 策略适配层管理，不等同于这些独立自定义能力。

该清单不能通过修改用户偏好、导入环境配置或填写测试报告启用能力。后续要启用原生能力，必须同时实现经过验证的 Android 后端、更新清单、适配器、验证脚本和回归测试。

### 活跃任务资源保护

`EnvironmentResourcePolicy` 是纯决策模块。前台、回复任务、上传、下载、导航、未保存草稿、缺少有效检查点的环境均不可成为暂停候选。决策模块不退出进程、不删除会话、不清理登录数据，也不执行任何环境操作。

`Budget.unmeasured()` 不设自动并发限制，不产生暂停计划，不代表已经验证可同时运行八个环境。可保存八个环境和同时运行八个环境是不同能力。`Budget.measured(...)` 要求具体设备范围、内核 revision 和测量证据哈希；其容量只适用于相同设备和相同内核。低内存时拒绝新分配，不中断已经运行的环境。

容量已满时，只有足够的后台闲置、检查点可靠的环境，才会得到 `ALLOW_AFTER_SAFE_SUSPEND` 建议。候选按最后使用时间排序。调用方必须在应用前重新检查实时状态和环境 generation；旧建议不构成暂停授权。

### 维护和 CI

`tools/gecko/check_identity_capabilities.py` 检查官方 SDK 清单、可选的原生原型证据、可选的真机容量记录以及发布元数据。文件都绑定大小和 SHA-256，路径必须位于仓库内。官方清单不能宣称原生能力已验证。

`.github/workflows/fingerprint-contracts.yml` 在 push 和 PR 中运行确定性 Java 策略测试和 Python 拒绝条件测试。CI 权限仅为读取，不发布、不合并、不发送消息。

```sh
bash tools/gecko/run_identity_host_checks.sh
```

运行需要 Java 17 和 Python 3.10+。输出位于 `work/identity-host/`。这些是主机策略和证据一致性测试，不代表真机、真实 ChatGPT 或网络性能验收。

## 应用接入

现有 `ChatSession.browserWorkActive()` / `updateBrowserActivity()` 已管理浏览器活跃和后台暂停。接入时可以调用：

```java
boolean keepRunning = EnvironmentResourcePolicy.keepActivityRunning(
    uiVisible, pending != null || operation || submitting || websiteReplyBusy,
    uploading(), transferActive, connecting || navigating,
    pendingSettings || identityApplyPending || auditRunning || serviceWork);
```

这条轻量策略只降低仍然保留的 Gecko 会话活跃度，沿用 `onPause` / `setActive(false)` / 计时器暂停。它不授权销毁会话、退出进程或实施并发限制。真实网页仍在生成回复、身份或设置待应用、自检和网络工作仍进行时，都应保留活跃度；已删除的会话由外层生命周期先排除。

若未来需要释放会话或进程，再使用更严格的检查点策略：

```java
boolean safe = EnvironmentResourcePolicy.canSuspend(
    uiVisible, pending != null || operation || submitting,
    uploading(), transferActive, connecting || navigating,
    latestCheckpointPersisted, draftUncheckpointed);
```

其他工作状态也要保护：待应用设置、自检、下载管理器中的任务、未完成附件选择、后台服务。任何状态未知时按仍有任务处理。现有 `GeckoWebView.checkpointReady` 表示启动检查点读取完成，不能直接作为最新草稿已经落盘的证明。

安全后台降活跃度可以沿用 `onPause` / `setActive(false)` 的现有流程。销毁会话或退出 Gecko 进程需要额外实现检查点保存成功的回执、活跃任务复核、恢复测试和 generation 校验；本包不提供自动销毁路径。

并发容量的默认状态保持未测量。只有真机报告验收通过后才接入 `admit(...)`；已运行环境重新选中时无需为其释放其他环境。如果容量建议要求暂停候选，先重新检查候选、完成保存与安全暂停，再重新计算准入结果。绝不能先创建新运行时再释放旧运行时。

## 原生增强原型的确切门槛

先从用户需求和 1.7 自检缺口选择一项能力。第一项优先评估独立时区；若官方 SDK 无法完整支持，再评估 Android Gecko 补丁。每次只做一项原型，验证后再考虑下一项。

原型需完成以下实际工作：

1. 固定上游 source revision、构建工具链和有顺序的补丁；在 ARM64 构建可复现 AAR。保留完整构建 recipe、日志、产物哈希。
2. 在真实 Android 设备、发布模式下测试页面主执行环境、同源 iframe、跨源 iframe、Dedicated/Shared/Service Worker。
3. 验证至少两个环境互不干扰、重启行为和配置回退。时区需包含 Date / Intl / 夏令时变化；Canvas 等能力需验证真实页面读取、图像导出和网站兼容性。
4. 验证 ChatGPT 登录、中文输入、长回复、附件、下载、工具、键盘旋转和后台恢复。网页服务决定会话和聊天功能。
5. 测量输入和恢复延迟、内存、耗电，并完成至少一次上游新 revision rebase 与设置降级演练。
6. 原型通过后再实现生产后端和正式能力状态。补丁未通过时继续官方 SDK；配置显示不支持，不能通过 JS 注入伪装成已完成原生控制。

可选原型清单保存为 `third-party/sdk/native-capability-prototype.json`。不随本包提供填有虚构结果的清单。格式要求：

| 字段 | 要求 |
|---|---|
| `schema` / `engineMode` | `1` / `patched-prototype` |
| `productionEnabled` / `sdkAarModified` | `false` / `true` |
| `sourceCommit` | 测试应用的完整 40 位 source revision |
| `upstreamRevision` / `rebasedUpstreamRevision` | 两个不同的完整 revision，证明已实际完成上游升级演练 |
| `capabilities` | 非空、唯一的已测试能力名列表，只允许清单中的五项 |
| `builtAbis` | 当前原型要求 `["arm64-v8a"]` |
| `patches` | 有序且非空的补丁文件记录列表 |
| `buildRecipe` / `buildLog` / `aar` / `deviceEvidence` | 仓库相对 `path`、正整数 `bytes`、64 位 `sha256` 文件记录 |

`deviceEvidence` 内容必须包含 `schema:1`、`status:"passed"`、`actualAndroidExecution:true`、`physicalDevice:true`、`releaseMode:true`、`synthetic:false`、匹配的 `sourceCommit`、`engineAarSha256` 和 `upstreamRevision`、真实 `deviceModel`、`abi:"arm64-v8a"`。

每条 `checks` 必须通过并附有带哈希的 `observation` 文件记录。每项能力需覆盖六种上下文名称：`page-main`、`same-origin-frame`、`cross-origin-frame`、`dedicated-worker`、`shared-worker`、`service-worker`。还需包含 gate：`environment-isolation`、`restart-persistence`、`chatgpt-compatibility`、`resource-budget`、`upstream-rebase`、`configuration-fallback`。

```sh
python3 tools/gecko/check_identity_capabilities.py \
  --prototype third-party/sdk/native-capability-prototype.json
```

脚本结果只表示文件和报告彼此一致，无法独立证明报告确实来自真机。报告必须经过实际执行和审查；原型验证不会启用生产能力。单纯填写上述布尔值或生成测试文件不构成验收。

## 实际设备容量记录

按具体设备测量两环境基线，再增加负载。至少覆盖前台输入、长回复、上传、下载和后台恢复。系统后台限制和手机锁屏需要作为恢复测试，不能承诺后台无限持续运行。

可选 `third-party/sdk/environment-resource-budget.json` 需包含：`schema:1`、`status:"passed"`、`actualAndroidExecution:true`、`physicalDevice:true`、`synthetic:false`、完整 `sourceCommit`、具体 `deviceScope`、匹配的 `engineRevision` 和 `engineAarSha256`、测量得到的 `maximumLive` 与 `minimumAvailableBytes`。

`runs` 的每条记录包含 `pass:true`、`liveCount`、不少于 120 秒的 `durationSeconds`、`scenario` 以及实际测量 `observation` 文件记录。目标容量下五种场景都必须覆盖：`foreground-input`、`long-reply`、`upload`、`download`、`background-restore`。正式测试还应包含设备信息、内存和交互延迟等原始样本以及采用预算的理由。

```sh
python3 tools/gecko/check_identity_capabilities.py \
  --resource-budget third-party/sdk/environment-resource-budget.json
```

120 秒只是拒绝瞬时伪容量记录的最低结构门槛。正式版本仍需更长的持续使用、锁屏恢复和实际用户操作测试。没有真机结果时保留未测量状态。

## 发布和持续维护

官方 SDK 构建继续使用现有 `verify_official_sdk.py` 检查实际 AAR/POM/sources 与 Gradle 解析结果。此包增加的清单验证可配合实际 AAR执行：

```sh
python3 tools/gecko/check_identity_capabilities.py --aar work/gecko-integration/geckoview.aar
```

发布阶段可检查 Gradle 版本号、source、既有 signer 标识、APK 文件名与实际字节：

```sh
python3 tools/gecko/check_identity_capabilities.py \
  --release-manifest work/gecko-integration/signed-public/release-manifest.json \
  --source FULL_SOURCE_REVISION \
  --apk dist/PocketChat-2.0.0-gecko-arm64.apk
```

signer 标识检查不能替代 `apksigner verify --print-certs`；原有签名和产物发布校验继续保留。主机测试也不能替代现有 Android CI。

若以后采用自编译 Gecko，不再将 AAR描述为“未修改官方 SDK”。需要另建自编译 SDK 锁文件、Gradle 构建输入验证和补丁回归流程。维护清单至少包括：上游安全更新、Android 服务和子进程适配、模板迁移、多个环境升级、旧配置降级、产物签名和真实设备验收。完成一次 rebase 后才能评估长期维护成本。

2.0 的原生能力是否进入正式版由上述证据决定；本包提供官方 SDK 阶段可运行的维护底座和拒绝错误能力声明的工具。

## 实际应用接入

ChatSession.browserWorkActive 现在使用 keepActivityRunning，活动回复以
当前页面、导航代次和只读 busy 状态判断；前台、发送确认、上传、下载、
导航和维护均保持活动。空闲只暂停仍保留的 Gecko 会话，不进行强制
退出、数据清理或内存驱逐。支持范围和模板详情显示原生能力清单。

## 交付与合并

执行 python3 tools/export-profile-upgrades.py --output work/profile-upgrades
可导出基于 v1.5.21 的顺序补丁、改动源码、实现说明与哈希清单。完整
Android 构建与 ARM/真实账户验收通过后才生成发布物。
