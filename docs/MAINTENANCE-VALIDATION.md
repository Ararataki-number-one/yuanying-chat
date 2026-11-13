# 浏览器维护验证记录

日期：2026-11-11；上传与深度维护记录追加于 2026-11-12。此记录对应暂停新功能后的导航修复与维护整理，配套说明见 [MAINTENANCE-AUDIT.md](MAINTENANCE-AUDIT.md)。

## 2026-11-13 发布收尾：保留失败，重新绑定最终源码

本轮基于 `1178ce488bc1532d71460845b2b7131724416df6`，完整树 `f1ba67d716596c4ed7d20cc39358f0d8d8c604ed`。恢复工作树时逐文件重建并核验该树，未用旧分支覆盖。版本仍为待发布的 `2.1.5 / 107`，正式版本仍是 `v2.1.4-gecko / 106`，直至原发布工作流成功。

该起点的完整结果已到终态，不能标为待完成或全部通过：

- [正式验收 43209949417](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43209949417) 的构建、lint 与 191 组 host 通过，随后桌面 Chromium 启动在原 12 秒内未就绪；下游完整发布证据没有生成。
- [profile 43211329412](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43211329412) 两个作业通过；主检查 1,624 项、caret 279、UI 46、readiness 17、发布协议 138 均无失败、错误或跳过。两 ABI 的 release/integration 与 SDK 检查完成，lint 0 errors、111 warnings。
- [界面维护 43211320952](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43211320952) 的维护作业通过。API 32 七个玻璃场景通过，后续录屏退出超时仍失败；API 35 有后台空闲帧和较早的设备操作失败。两 API 的独立 Chromium 界面检查通过，不替代 Gecko 场景。

原始 API 35 后台文件记录为 PAUSED、仍可见且至少一个窗口 visibility=0。本轮新增准备检查明确拒绝该原始输入；STOPPED / 全隐藏的变体只作为受控宿主边界，不能写成设备观察。准备阶段不读取帧计数决定何时通过，原零新增帧的 quiet 窗口及超时不变。交叉检查另补齐未知重复字段、各处 resumed 记录和根窗口总数的一致性；新增组 14 项与原工具 73 项在本轮工作树重新执行。

原 `09e3db4` 的冷启动记录仍保留展开状态和缺失 compact 首次点击的原值；新契约验证真实地址入口，不能把旧失败改写成成功。附件宿主使用原 `1178ce4` 方法的完整限定片段作负控，固定字节摘要，避免新测试依赖浅克隆未包含的临时父提交。导航、菜单、冷启动、文件、进程和录屏各组的定向运行分别保存实际输入与结果；它们不合并成整套设备通过。

本轮采用逐文件不可变 Git blob 保存已经通过的维护切片，最终完整提交再运行原正式验收。中间带 `[skip ci]` 的保存提交不作为发布候选，也不代替最终检查。正式发布必须使用同一最终源码的完整 APK 和最后完整证据提交，核对 run、attempt、版本、原签名及所有要求的作业。缺失的旧 stderr、未确定的录屏退出原因和物理手机验证继续如实保留。

## 2.1.5 准备阶段：本地回归与上轮终态

本轮从 `d02457f2344c9eb439758507fb9dfe39cd72b7d5` 继续，准备 `2.1.5 / 107`。下述定向检查来自包含新补丁的工作树；不能把父提交当成新 APK 的源码。统一回执、完整 APK 与设备结果由新提交 CI 另行绑定，最终发布入口见 [PR #7](https://github.com/Ararataki-number-one/yuanying-chat/pull/7) 和正式 Release。

| 生产行为范围 | 本轮定向结果 | 原问题复现 |
| --- | --- | --- |
| 当前 `Attachments` 选择器与结果归属 | 52 / 52，11 个编译负控 | 原代码成功编译，37 项中 23 项失败 |
| 当前 Gecko 临时启动窗口 | 73 / 73，11 个编译负控 | 原版 56 项中 27 项失败；补充晚打开场景后首版补丁新增 10 项失败，修复后通过 |
| 原 Gecko UI 生命周期 | 原 53 项及新增异常清理 2 项通过，17 个原负控保留 | 验证回调异常不截断其余清理 |
| 原 addon / 时区路由 / 通用路由持有 | 51 / 167 / 171 项通过，保留各自负控 | 仍执行当前生产方法，普通页面委托明确锚定 `newSession()` |
| 原页面恢复 | 161 项，7 个编译负控；内嵌 reload-request 131 项 | 临时启动窗口是显式 SDK 边界，完整行为由新启动宿主执行 |

这些回执不代表 Android 原生窗口或真实账户成功。Gecko 原因定位另使用固定上游源码的因果探针；最终启动效果仍需同源设备作业确认。原签名文件已核对，证书 SHA-256 为 `f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`，签名一致也不能替代行为验收。

上轮 `d02457f` 的实际 CI 终态已确认：

- [维护工作流 43165241474](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43165241474)：当前维护 31 / 31 组通过；API 32、35 两组设备作业最终均失败，不再是待完成状态。两版本的 Chromium 原生界面检查通过，不能覆盖 Gecko 的失败。
- [完整 SDK 构建 43165247441](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43165247441)：两 ABI 的 release / integration APK 及 lint 完成，lint 0 errors、111 warnings；host-contracts 仍失败，1,562 项中 60 failures、78 errors、1 skipped。
- 上轮 API 32 的七个场景均在原路由桥接尚未就绪时超时；横屏实际 2472 × 1236，没有达到 2676 × 1236。API 35 存在就绪事件未从 logcat 找到及空闲帧超预算。此次分别处理启动依赖、事件记录和旋转配置，没有降低空闲绘制标准，也不提前声明设备修复成功。

历史证明迁移保留旧对象、断言、fixture 与负控，当前行为检查继续使用当前源码；完整 discover 必须重新执行。原 2.1.4 的发布结果、旧提交的成功构建和本地定向回归均不能替代本次完整发布流程。

### 候选 `e96a827` 暴露的问题与后续维护

候选源码为 `e96a827934431d933fb51ecf3189c33415bf908a`，树为 `ae8cffbfe26cce0a04e5f6fc5938fa3914a24bfa`。它不是可发布的验收结果：

- [源码与 APK 工作流 43190316763](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43190316763) 完成两 ABI 的 release / integration 构建、lint 与 SDK 身份检查，但 host discover 的 1,587 项仍有 1 failure、21 errors。20 个错误来自干净 checkout 没有准备两份原 UI 历史对象；另外两项仍把当前文件用于原整文件历史证明。
- [完整发布验收 43190735715](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43190735715) 在浏览器宿主组失败；后续设备作业没有执行。不得把创建出的作业名称称为已完成的 13 项验收。
- [API 32 / 35 作业 43190309401](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43190309401) 的当前维护 34 组通过。API 32 六个进入就绪等待的场景均进入实际 Gecko 文档，Chromium 两场景通过；但玻璃七场景只有两项通过，另有空闲绘制、横屏字体观测重复、系统导航栏缺失问题。API 35 六个竖屏场景被实际横屏配置拒绝，唯一横屏场景仍有 9 帧空闲绘制，独立 Chromium 界面也因横屏残留失败。

后续修复继续保留上述失败回执：

- 默认历史准备入口纳入原有两个 UI owner 的 23 个文件，复用原固定清单、Git 对象与摘要核验。PR 构建按真实 PR head 验证，不改写 `GITHUB_SHA`。原缺对象场景红测为 1 failure / 1 error；新增与原准备检查共 62 项通过，实际 CLI 同时验证原 21 owner、两个 UI owner 和 checkout 未变。
- 浏览器偏好和阅读返回宿主补齐当前真实方法协作。偏好组两种 JSON 各 57 项、阅读组 124 项通过；过时的“冷启动必须强制主页”断言改为保留浏览器环境的恢复入口，其余原断言保留。实际 Android 页面仍由设备验收检查。
- Android 15 的窗口日志显示，桌面的 `NOSENSOR` 覆盖退出时恢复旧横屏，覆盖了在桌面执行的旋转命令。配置现在先让原有原生网络 fixture 进入前台，再设置自然轴和旋转，并读取真实配置、字体和视口；两次稳定观测之前不启动字体 nonce。该页面仅用于模拟器配置，不是界面通过证据。15 秒共用期限也覆盖最后解析与接受，失败恢复仍关闭配置页面。
- API 32 的原始窗口记录确实没有导航栏 InsetsSource。AVD 明确配置屏幕导航键，并保留实际 AVD、运行硬件配置、系统属性及窗口记录；原“双系统栏来源必须存在”的门槛保留。配置 5 项宿主检查通过；显示工具 67 项及原截图解析 23 项通过。这些结果不能代替重新运行设备作业。

重新提交后的完整结果必须绑定新源码、run 和 attempt。本文保留各次失败与修复的边界，最终可发布状态由同源 CI、完整发布证据和签名验证共同决定。

### 纹理生命周期的定向验证与完整门禁

`GeckoTextureSurface` 的因果检查直接执行固定派生 SDK 的完整类字节。原逻辑收到 12 个同纹理、同尺寸内容更新时，表面提交由 1 增加为 13，同时额外创建 12 个 `Surface`，触发原行为断言失败。适配后，实际 SDK 模式与完整固定官方协作源码模式各通过 60 项（41 项生命周期、19 项显式恢复）和 15 个编译后负控。内容帧计数属于明确的 Android 边界模型，不是实际 GPU 呈现或设备帧率证明。

独立审查发现最初的重复帧过滤还会截断 SDK 的显式表面恢复请求，19 项恢复红测中有 10 项暴露该问题。最终实现保留公开 `requestNewSurface()` 的异步 SDK 调用，用独立的一次性标记允许下一次有效更新重建表面。实际应用和 caret fixture 的 override 均由宿主提取执行；周围的 View 调度仍为明确的边界。正常销毁按 Android 的先回调、后释放与清空顺序建模，直接回调中的合成重入另行标注。原 caret 输入诊断 17 项通过，其全部原测试方法体和 fixture 原 IME 方法未变。

原启动窗口宿主仍为 73 项与 11 个编译后负控，实际执行输入未变化。新组件整类另通过固定官方 Android 35 API 编译，未使用 Android stub 代替该编译依赖。强制 SDK 模式缺少 receipt、缺少 AAR、错误 JAR 或 receipt 被改动时均拒绝。

当前维护入口加入这一组和真实模拟器配置检查。完整浏览器入口保留原 190 个命令、顺序、输出目标和 300 秒预算，尾部增加必须读取真实 SDK 的第 191 组；独立声明测试执行原／当前注册代码，逐项比较前 190 个 argv，并拒绝删除旧命令、把新组改成可选 SDK 或放宽子进程预算。

本地原 190 组诊断的前 112 组通过，第 113 组历史输入修复后通过；原后段 77 个命令全部执行，其中 76 通过，`public-source-history` 超过原 300 秒。诊断期间有并行源文件修改，分段结果不合并为整套通过。单次 Git trace 显示，本地完整旧树重复打包约 82 MB，用时 13.43 秒；原正式 [2.1.4 build 作业](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/42965461191/job/130341523075) 的同组实际耗时 169.926 秒，原 190 / 190 通过。保留本地超时与原预算，最终重新执行同源完整 191 组。

### 候选 `b6a7273` 的完整构建与剩余准备问题

源码 `b6a727363783bb7d4c22e96dace73f4f52b08b27`，树 `ac1e41e86b0ee0d104aed59a3c1026f3430f779e`。下述结果属于该候选，不属于之后的准备修复：

- [当前维护与设备流程 43200807281](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43200807281) 的维护 35 / 35 组通过，2,008 个输入前后不变并逐一对应真实 Git blob。两 API 的 release / integration、lint、APK 印记与 SDK 构建检查均通过。
- [独立 SDK 与 profile 流程 43200815210](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43200815210) 完整构建通过；lint XML 与上一维护提交 `d02457f` 的原 XML 字节相同，为 111 warnings / 0 errors。profile 主体 1,601 项、caret 279 项、界面采集 46 项均通过。之后独立 readiness 16 项仍有两个子项报错，因此整个 host 作业未通过。
- API 32 在安装应用前仍显示 `FallbackHome`／`ImmersiveModeConfirmation`，启动后 System UI ANR 挡住初始应用与 Chromium 界面。七个玻璃场景均未开始；已记录的两个系统栏来源说明屏幕导航栏配置生效。没有 ANR 线程栈，不宣称已经定位系统进程挂起的底层原因。
- API 35 七个场景的实际方向、尺寸和字体配置已稳定，但新的字体 nonce 均为零条记录，横屏 loading 仍停在网络页面。原命令的 stdout 长度与 SHA 精确匹配包含“intent has been delivered to currently running top-most instance”的启动输出；这是由固定输出格式恢复并逐字节核验的内容，不是另存的原明文日志。准备页面的旧实例接收新 intent，没有执行新动作的创建分支。独立 Chromium 两场景通过；七个场景均未到 Gecko 空闲帧检查。

后续最小修复保留这些失败：readiness 的两个当前完整方法先逐字比较正式版对应方法，再把固定历史整文件送入原逆证明；其他七个方法和原负控保持当前来源，17 项与后续发布协议 138 项通过。紧邻三个 whole-source 历史测试仅调整两处读取操作数，原证明和负控不变，3 / 3 通过。

正式流程尚未执行到的 compact capture 宿主也在定向诊断中复现旧整文件文案约束：当前 UI runner 的两处“会话”文案已改成浏览器入口。历史整文件证明固定到真实正式对象，当前 compact 的完整消费者、触摸、超时、菜单与协作函数仍直接比较；两种原 JSON 各 44 / 44 通过，原九个相邻测试方法未改，新增语义负控后 12 / 12 通过。其余诊断结果不合并成正式流水线成功。

新 HOME 准备函数 12 项、原 AVD 5 项通过。配置页面释放另保留原 67 项检查，新增六项在原 helper 上实际失败、修复后 73 / 73 通过；停止操作仍使用配置观察的原 15 秒共享截止时间，失败或迟到不能标记成功。工作流保留原 12 分钟设备准备与 30 分钟场景预算；字体 nonce、实际视口、40 秒业务就绪以及原帧数门槛保持原值。最终仍须在新源码上重新完成全部构建与设备验收。

### 候选 `09e3db4`：全量 profile 与保存宿主的诊断边界

源码 `09e3db4e9eaf9b2ca353e35479b2d1022487329b`，树 `02036a538758164c6348cea9fdc98398132331ed`。独立 [profile 工作流 43206509868](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43206509868) 的两个作业均成功：主检查 1,616 / 1,616，caret 279、UI capture 46、readiness 17、release contract 138 全部通过，无 failure、error 或 skip。两 ABI 的 release / integration APK、SDK 身份和 lint 均通过，lint 为 0 errors / 111 warnings。这些 APK 属于该 profile 运行，不作为正式流程 APK 的替代。

[维护工作流 43206499027](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43206499027) 为 34 / 35 组通过，2,010 个声明输入均与该提交的 Git blob 一致且执行前后不变。唯一失败为 `saved-file-copy`：原 runner 在解析 JVM stdout 时抛出 JSONDecodeError，未产生要求的结果文件。原 stdout / stderr 虽写为 `.txt`，但当时工作流只归档 JSON 与 log，无法追回该次 JVM 错误；不能据此断定具体生产行为失败或线程竞态。

随后独立确认宿主 `Fixture.idle()` 的退休竞态：真实单线程 executor 在检查状态之后、提交屏障之前由真实 `close()` 关闭，原代码成功编译后必然抛出 RejectedExecutionException。修复后新增 8 项检查通过，包含真实排空与原 UI 屏障、已经退休、运行中拒绝、真实失败 Future，以及活动／退休 worker 的原五秒失败；用 latch 和 future 固定顺序，没有通过反复抽样获得结果。这个反例没有恢复旧 CI 丢失的 stderr。

原 `CopyHost` 除 `idle()` 外逐字不变，51 / 51 行为检查通过且输入未变，原 Java 子进程 45 秒预算保留。新 runner 记录退出码及两条原始输出流；无效 JSON 原样报错，非零退出不能产生通过状态。维护入口在原 `saved-file-copy` 组追加这 8 项，原 35 组均保留，工作流另外归档 `.txt`。这些收尾修改仍须由新提交完整执行，不能将 `09e3db4` 的部分结果合并为新提交发布资格。

## 第四轮深度维护：界面、权限和文件生命周期

起点为 `2ef73a275f4db849cf2ee5b740c2ed4055042699`，源码树 `58707a2518d92a1353682e687b97648269c0301c`。本轮只维护当前代码，版本保持 `2.1.4` / `106`。以下定向检查先复现原代码行为，再验证修复；整体验证与上传后的 APK 必须分别绑定本轮实际输入和新提交。

| 验证 | 原代码行为证据 | 修复后定向结果 |
| --- | --- | --- |
| browser-permissions | HEAD 原源码成功编译，同网址刷新重入触发指定断言失败 | 62 / 62，原 43 项保留，新增 19 项 |
| gecko-ui-lifecycle | 原组合成功编译；首份 39 项中 16 项失败，补充 pause 重入后 44 项中 20 项失败 | 53 / 53，17 个负控均成功编译后由行为断言拒绝 |
| download-cancellation | 原组合成功编译，42 / 53，11 项失败 | 60 / 60，原 37 项保留，新增 23 项 |
| saved-file-copy | 原组合成功编译，33 / 42，9 项失败 | 51 / 51，原红测 42 项保留，新增 9 项拒删检查 |
| download-persistence / download-recovery | 保留原 fixture 与断言 | 39 / 39 和 42 / 42 |
| display-acceptance | 保留原观测、40 秒 ready 时限、交互路径与预算 | 两个工具组 23 + 49 = 72 项；后者原 40 个方法 AST 不变 |

UI 生命周期检查执行当前 `createChatUi`、`remoteClient`、生命周期方法、会话客户端、附件/下载安装销毁及 Gecko 回调分派；新绑定组件整类执行。引用遍历是确定性的宿主对象检查，不是真机 heap 分析。权限检查使用当前完整生产类，原 fixture 除新增方法及其调用外逐字保留。

文件检查执行真实 Java 生产方法、JVM worker、文件租约与测试文件，Activity、偏好实现和文件提供方是声明的边界。原 persistence / recovery fixture 逐字保留；唯一接口迁移是 persistence runner 提取当前真实 `retirePrivateCopy()`。未更改原断言或历史源码投影。定向并行检查曾因 JDK `hsperfdata` 锁警告污染 stdout，被旧 runner 的严格 JSON 解析拒收；关闭该 JVM 诊断计数器后顺序重跑通过，没有放宽解析。

### 统一入口与证据范围

`tools/browser/check_maintenance.py` 在原 25 组基础上加入权限、UI 生命周期、下载取消、下载持久化、下载恢复、另存为，共 31 组。新增的 `GeckoUiBinding` 也列入可选的原生 Java 编译清单。完整 APK 构建仍使用实际 Android / Gecko SDK，不以生成的编译边界替代。

冻结后的统一入口 **31 / 31 组通过，34 个命令均返回 0**。UTC 2026-11-12 05:54:25 至 05:59:57，耗时 **332.219 秒**。**1,985 个执行输入**、依赖与 HEAD 前后一致，`executionInputsUnchanged=true`、`changedInputs=[]`。执行时为上述起点加本轮未提交变更，`dirtySource=true`；不能用起点 SHA 冒充修改后的身份。

总回执为 `/workspace/scratch/d82e7decf2fd/maintenance-validation/round3-final/results.json`，SHA-256：`0b126067cebde21fd0d5313ca82bdeb8ef5cf7cf40bd3465069304c333023180`。这次完整顺序运行中，原下载持久化与恢复组均正常生成回执，无须改变解析或 JVM 选项。

定向证据另位于 `maintenance-validation/round3-permissions`、`round3-browser`、`round3-download` 和 `round3-ci-audit`。使用 Temurin 17.0.21+9 与固定 JSON jar，SHA-256 为 `3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796`。本地没有执行可选完整 Android API 编译、APK 或设备运行；上传后的新提交结果追加到 PR #7，不能沿用旧提交的 APK。

### 上轮 `2ef73a2` 的最终 CI 状态

- [current-maintenance 作业 130974413774](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43155512845/job/130974413774)：25 / 25 组通过，349.777 秒，1,971 个输入不变、`dirtySource=false`。回执 SHA-256 为 `bfafdbc13ff7d39cb264733e2641ae04d9da00963660472d79b29f828a8411d9`。
- [official-sdk-build 作业 130974440252](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43155521692/job/130974440252)：完整 release / integration APK 与 lint 成功，lint 0 errors、111 warnings；原生 SDK 与实际解析 AAR 身份核对成功。
- [host-contracts 作业 130974439767](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43155521692/job/130974439767)：1,562 项，60 failures、78 errors、1 skipped，138 个失败标识；127 项历史源码/AST 合同、10 项缺固定历史 Git 对象、1 项缺固定 Android 35 jar。旧启动 fixture 缺接口已在第三轮消除；其余失败没有消失。
- [设备工作流 43155512845](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43155512845)：API 35 玻璃 4 / 7，长按环境 7 / 7 都通过；阅读 5、9 帧超预算 2，后台 1 帧超预算 0。三次追加诊断均零绘制，但不能覆盖此前窗口的失败。API 32 横屏 2472 × 1236 与要求 2676 × 1236 不符，正确拒绝且恢复尺寸已验证；随后 7 / 7 未取得 ready，fixture 请求为零，未进入交互或空闲测量阶段。两个 API 的独立 Chromium 原生界面 smoke 均 2 / 2，通过不代表真实网页或保护策略已验收。

设备审计回执 `round3-ci-audit/device-audit.json` 的 SHA-256 为 `847f54781e6f8410cacfb84d020b5dc90d2a43e452cce5fea9d52ac618a8908a`。本轮只补充 ready 失败后诊断，不声称已经修复 API 32 启动或 API 35 绘制问题。未修改等待期限、绘制预算、历史 pin、工作流或正式玻璃实现。

## 第三轮深度维护：冻结后的当前源码检查

本轮从 `b389db2da1b53c26ce83c3c9415be9fb515303b1`、源码树 `efa3482cc8408eb51a2bf3f8782bac77297db541` 继续，保留此前导航、指纹事务、网络租约和集成接点修复。正式基准、版本 `2.1.4` / `106`、默认 ChatGPT 主页、两种内核接入和玻璃实现不变。

统一入口 **25 / 25 组通过**，UTC 2026-11-12 04:23:52 至 04:29:17，耗时 **324.984 秒**。执行时为上述父提交加尚未提交的维护变更，回执明确记录 `dirtySource=true`；不能把父提交名称当成本轮修改的源码身份。**1,971 个输入文件**逐项 SHA-256 前后相同，`executionInputsUnchanged=true`、`changedInputs=[]`。

这次输入清单覆盖生产代码、测试及其同目录 fixture、工具及导入脚本、资源和构建配置；包含指定目录内尚未加入 Git 且未被忽略的新文件，也检测运行中的新增与删除。文档不在执行输入内。没有声称扫描被 Git 忽略的任意文件。

| 新增或同步的验证 | 本轮结果 | 证明范围 |
| --- | --- | --- |
| reply-task-persistence | 127 / 127 | 完整当前 `DeliveryStore`、`WebReplyObserver`、无状态协调类及原样抽取的三个 `ChatSession` 入口；数据库失败、偏好内存/磁盘分离、同步回调重入、冷恢复 |
| gecko-activation | 50 项行为检查，17 个编译后负控通过 | 当前完整 `activate`、`closePopup`、`closeWebsitePages`、线路退役，以及真实桥接请求与租约类 |
| browser-startup | 46 项宿主断言通过 | 当前真实 `BrowserActivity.resume` 与环境入口；恢复既有浏览器、保留网址、重排现有任务 |
| display-acceptance | 23 + 40 = 63 项通过 | 默认 display 0 的实际窗口尺寸/DPI、请求值与观测值分开记录、严格拒绝不匹配配置；原 54 项测试保留 |
| 已有 page-lifecycle / reload-request / deferred-wake | 44 / 131 / 30 项通过 | 原场景主体逐字保留，仅同步完整协调类所需边界；原 blank-final 编译拒绝负控仍成立 |
| 其余已有维护组 | 全部通过 | 导航、桥接归属、Chromium 指纹事务、网络租约、环境配置、页面恢复等重新执行，不沿用旧绿灯 |

持久化红测使用与 `b389db2` 一致的原生产源码，成功编译后为 **47 / 111，64 项失败**；部分异常提前结束单个场景，因此不能说旧版执行了修复版全部 127 项。Gecko 分别保留两份成功编译后的失败回执：原 `activate` 覆盖回调中新导航，以及修复 `activate` 但保留原 `closePopup` 时误关新导航所在页面。不是用编译失败代替行为反例。

启动宿主原来缺少 `BrowserActivity.resume` 接口。此次抽取实际当前实现，原两个“强制打开主页”的旧预期明确迁移为恢复当前浏览器，并增加任务重排断言。没有改变应用的默认主页。

### 本轮本地回执

目录：`/workspace/scratch/d82e7decf2fd/maintenance-validation/round2-final`。

| 回执 | SHA-256 |
| --- | --- |
| 25 组 `results.json` | `cd08fefeb69aa58dd360eb70ed9bfe218ac21346e9346051b87a5642a202ffcc` |
| `reply-task-persistence.json` | `5f1a4f472899f4ef18f944098a3a9fa9cc8b8aa817a10ff791d01c885c6ebbd1` |
| `gecko-activation.json` | `348c3bb9202e24077b77e26d912d5d4ca7a266500124c8f20ae9cbbe44447880` |
| `session-navigation.json` | `482025fd5735f65badee2761e30abc793a9a1311bb0ff974ee059d9d8959682a` |
| `browser-startup.log` | `ff4f00a97256bce11b04344bcbc5ef9f66f0fb579a7c432a214b565fc3c75454` |
| `display-acceptance.log` | `9595d80c9471e830a6e4a16ca011ca851eba10502e40e0f38f7f7707c2d9446e` |

本轮使用 Temurin **17.0.21+9** 和 `json-20250517.jar`，后者 SHA-256 为 `3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796`。本地没有运行可选 Android API 编译组，回执 `actualAndroidExecution`、`fullAppBuild`、`fullReleaseQualification` 均为 `false`。存储检查底层是限制 SQL 形状的文件模型；没有验证真实 SQLite/WAL、Android 偏好实现或系统通知全局一次性。新提交的 APK、lint 与设备检查由原 CI 工作流执行，结果追加在 PR #7，不能引用下方旧提交的 APK 作为本轮产物。

### 上轮 `b389db2` 的最终 CI 状态

为避免把上一轮待完成结果误读为绿灯，补齐实际终态：

- [current-maintenance 作业 130893701690](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43130666820/job/130893701690)：**21 / 21 组通过**，225.852 秒，424 个输入不变。
- [official-sdk-build 作业 130893730827](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43130675765/job/130893730827)：完整 release / integration 编译、APK、lint 与 SDK 身份核对通过；lint **0 errors、115 warnings**，测试包和临时签名不等于正式发布。
- [host-contracts 作业 130893731189](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43130675765/job/130893731189)：1,562 项，61 failures、78 errors、1 skipped。最终失败头去重 139 项：127 项历史源码/AST 合同，10 项缺历史 Git 对象，1 项旧启动 fixture 缺 `resume`，1 项缺 Android 35 jar。此次只修复已复现的启动 fixture；没有禁用或改写其余旧门禁来制造全绿。
- [API 32 / 35 设备工作流 43130666820](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43130666820)：两组玻璃设备验收均为 **3 / 7 通过、4 / 7 失败**；两版本的 Chromium 默认及窄屏大字场景均通过。部分阅读空闲绘制超预算、API 35 长按误入网址编辑器仍是未解决验收项。

API 32 横屏窗口实际为 **2472 × 1236**，请求为 **2676 × 1236**。旧工具以请求宽度测量，产生错误的导航中心偏移 `-102 px`；按真实窗口回放偏移为 `0 px`。本轮工具会在请求与观测不匹配时明确停止并报告配置失败，**不会把实际 824 dp 当作要求的 892 dp 场景验收通过**。原 14 份设备窗口记录已回放核对；未增加等待预算、放宽长按或空闲帧验收条件。

以上旧 CI 结论只绑定 `b389db2`。它们为本轮定位提供证据，不构成本轮已通过设备验收的声明。

## 上传后的完整 APK 构建

第一轮导航补丁已上传为 `0a95be3d15e42c679343d9a6caa7bdea6758bcf9`，源码树 `2811d7e3f34cde413be5337b4fc4c2e18c35f5ba`。该树与下面 18 组原始回执记录的 409 个输入逐一一致。版本保持 `2.1.4` / `106`，PR #7 仍为 Draft。

- [浏览器工作流 43125924155](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43125924155)：API 32、35 两组均通过完整 `assembleRelease`、`assembleIntegration`、`lintRelease` 以及源码 / APK stamp 检查。
- [SDK 构建作业 130877864561](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43125931795/job/130877864561)：整作业通过。原 `build.log` 显示上述任务与 `writeCaretResolvedArtifacts` 实际执行并 `BUILD SUCCESSFUL`，不是缓存的旧提交结论。
- 原生 SDK 仍为 `local.pocketchat.sdk:geckoview-caret:157.0.20261005135250-pocket3`；实际解析 AAR SHA-256 为 `f9fad20c02e554b00da51b72c8cd2643e121b4a81bc656dd5cf03de21ded2e72`，`gradleResolvedAarVerified=true`。
- release 与 integration 两种 ABI 均构建；测试包名为 `local.pocketchat.test`，使用临时测试签名，不是正式更新发布。release APK 中没有测试 stamp。

构建回执 `ci-0a95be3-build-receipt.json` 的 SHA-256 为 `88d9a3de20ceff0ae2b68641ca112a1aa8667ee33bc043994a7bb300a81e8f5e`，来自实际 Actions 原始日志及已核对 ZIP 摘要的构建制品。

lint 没有 error，仍有 **115 条 warning**。与父提交 `815f7fee` 的 114 条按诊断 ID、消息和文件比较，增加一条 `WebReplyObserver.archiveNavigation` 的 `ApplySharedPref`：偏好监听器重入后恢复 `pending` 的提交未读取返回值。不能机械改为 `apply()`，其持久化失败语义应与任务终局单独整理。

全量宿主检查仍失败：[host-contracts 作业 130877864935](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43125931795/job/130877864935) 的主 discover 实际运行 1,560 项，65 failures、70 errors、1 skipped。按最终失败头去重的 135 项中，117 项属于历史源码 / AST 身份及其保留合同，10 项缺少固定历史 Git 对象，1 项缺少 Android 35 编译依赖，7 项是当前宿主协作接口缺失；其中 Dashboard 启动入口缺失在父提交已存在，本轮导航变更另暴露 3 组、6 项接口迁移遗漏。它们需要按实际接口修复，不能由新增当前维护作业的通过结论替代。

以上完整 APK 结论仅绑定 `0a95be3`。后续深度维护修改必须另有对应新源码的验证和 APK 结果，不能沿用本次构建成功。

## 第二轮深度维护的本地验证

统一入口 **22 / 22 组通过**，运行时间 **385.806 秒**，UTC 00:34:41 至 00:41:06。**426 个生产与宿主输入**、全部依赖和执行期间 HEAD 前后一致，`changedInputs` 为空。

执行时 HEAD 是 `0a95be3d15e42c679343d9a6caa7bdea6758bcf9`、工作区含尚未提交的深度维护变更，回执如实记录 `dirtySource=true`。实际执行内容由逐文件哈希绑定，不能将父提交当作本轮生产修改。下次完整 APK 与 CI 当前维护作业必须绑定新提交。

证据目录：`/workspace/scratch/d82e7decf2fd/maintenance-validation/deep-final`。

| 回执 | SHA-256 |
| --- | --- |
| 22 组 `results.json` | `9dcefb9acfdbb0888ed557e0fb003da4753c19e974d8350516207377d1ac0caa` |
| 68 个完整生产 Java 类 `native-compile/receipt.json` | `73566432bbe96270557f28ad0e0beaf8c48a9774a6cfb09b62e8fd47256e3986` |
| 三组当前宿主接口迁移汇总 | `f78e631882beddf0190cc1ba0972b16b09bbab6d16ad5a65f970439b890e787c` |

### 主要新增 / 扩展检查

| 组 | 本次实际结果 | 验证内容 |
| --- | --- | --- |
| chromium-navigation | 316 项，8 个编译后反例 | 原 276 项保留；新增 11 项失败停网 / 重入，29 项实际 load / save / validate / ensure 调用 |
| chromium-fingerprint-jobs | 32 项，4 个编译后反例 | 完整 Jobs + Store / Spec，快照、串行事务、CAS、关闭排空 / 禁止旧交付、执行器拒绝 |
| route-start | 65 项 | 原 43 条名称和顺序保留；22 条新租约与连续启动边界 |
| route-terminal | 8 项 | 实际终局观察器与当前启动方法 |
| route-lease | 48 项 | 实际租约、准入、候选与释放唤醒 |
| native-compile | 68 个完整类，262 个编译边界文件 | 新 Jobs 已加入完整生产类；Android / WebKit / SnakeYAML 均为实际依赖 |

其余第一轮各组仍包含在本次统一执行中并通过；不以旧回执代替重新执行。当前维护 CI 作业不传三个原生编译依赖，因此执行 **21 个宿主组**；完整 APK / lint 在同工作流原有独立作业执行。

原缺陷均先用修改前源码成功编译并触发指定失败：保护模式自测结果写盘失败仍放行，以及第二轮重启过早释放变更租约。对应原始回执为 `deep-audit/fingerprint-receipt-failure-new-head.json` 和 `deep-state/red-before-fix.json`。

### 针对实际 CI 接口遗漏的补充验证

以下单独回执不混入 22 组计数：

- PageBridge：桌面及 Android JSON 各原 32 项 + 独立导航 dispatch 4 项通过；原四个可编译反例分别在原 32 项中得到 28 / 26 / 29 / 31 项通过，均按预期被拒绝。
- SourceCaseHandoff：两种 JSON 各原 36 项通过，observer 与 deadline 守卫保留。
- ResourceRetirement：38 条原契约 + 2 条有明确理由的当前所有权迁移，共 40 项；原 8 条 pending、原 2 个负控与新 2 个负控通过。旧 / 新谓词逐条保存在 `resource-navigation-ownership.json`，见维护审查中的迁移说明。
- 当前 network-core 提取入口 28 项通过，回执 `deep-state/network-core-final.json` 绑定下面最终 NativeNetwork 哈希。

这些测试迁移对应第一次上传 CI 中本轮新增的 6 个当前宿主编译失败；旧 Dashboard 入口与其余历史校验未更改，也没有据此宣称全量 discover 已通过。

补充验证使用的 Android JSON 为 `android-json-0.0.20131108.vaadin1.jar`，SHA-256 `dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79`。统一 22 组仍使用固定的桌面 JSON。其他 JDK / API / WebKit / SnakeYAML 版本与下方第一轮依赖表相同。

### 22 组冻结时的三个生产文件

| 文件 | SHA-256 |
| --- | --- |
| `BrowserActivity.java` | `0ecd479e779fb656227000a18c3d9615d53785f9ec37a96faf098a9c89d83494` |
| `ChromiumFingerprintJobs.java`（新增） | `628797b8d258a95db775ad9976cc74ceccbc2992075cd004929ea17711d12180` |
| `NativeNetwork.java` | `b15ac95e7a6555f98dff2a43d8c3c58b0c9bda067b3aea7f430ddc147d808dd9` |

本轮不修改 Gecko、ChatSession、玻璃渲染、版本、更新源或签名。上述宿主与 API 编译回执均不代表 Android / Gecko / Chromium 实机运行；旧页 JavaScript 的立即停止也不在资源宿主证明范围内。

## 集成测试接点同步与 APK 重试

深度维护已上传为 `7f5f90190c0e733f73b1ea51d97d32ce7e052e52`，源码树 `ed8098e664488b65a220094adb87832b80789e81`。

该提交的 [current-maintenance 作业 130889823139](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/43129448758/job/130889823139) **21 / 21 组通过**，336.107 秒，424 个输入文件前后不变；原始 `results.json` SHA-256 为 `1a1294e40ef5c34f572ebf7dec2a66220bbd7503fc8966b9135165217fff13be`。

完整 APK 检查没有通过：两个浏览器构建和 reviewed SDK 构建均在 `compileIntegrationJavaWithJavac` 发现同一编译错误。`WorkerPolicyIntegrationActivity` 的真实 JavaScript 迟到回调测试仍直接访问已经移走的 `fingerprintWorker` 字段；release Java 已编译，但 integration APK / lint / stamp 未完成，不能称为完整构建成功。

后续修复仅增加生产协调器工厂接点并迁移该集成 fixture：

- 默认工厂使用原应用环境 Context 和主线程交付器，生产构造行为保持原样。
- fixture 私有单线程队列注入真实 Jobs；原 8 秒 fence 与实际保存 CAS 共用该队列。
- 原 Worker check 表达式、JavaScript 观测 / 保存 / 等待顺序和 `onDestroy` 方法未改；先释放 latch，再由 Jobs 排空并关闭队列。
- 不暴露 Jobs 私有 worker，不添加任意排队接口，也不恢复 Activity 裸线程字段。

工厂接点版本的 **68 个完整生产 Java 类 API 编译再次通过**，回执位于 `deep-integration-followup/native-compile/receipt.json`，SHA-256 为 `ca3c2ef9903409233f85ea58fa1ba612f068e2c5e933dc039ba07ea1742727f6`。输入前后不变。该检查不含完整集成 APK，最终仍须以下一次对应提交的完整 CI 构建为准，结果更新在 PR #7。

此跟进后 `BrowserActivity.java` 的 SHA-256 为 `40dc87fd23e850ee6b585021b3720a4836b50e9e37c7b1f7fb551e4c1e3f0b89`；`WorkerPolicyIntegrationActivity.java` 为 `93d108adde4a7f4cefc2d4f9991723706a80fedcba722a26e4c8fc5bc51a183c`。Jobs / NativeNetwork 与上面的 22 组冻结输入一致。原 22 组回执继续保留其真实源码哈希，未重写成已执行工厂跟进版本的证明。

## 第一轮宿主结果与源码归属

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
