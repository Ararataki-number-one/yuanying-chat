# v1.6 环境配置实现与合并说明

本实现基于正式 `v1.5.21-gecko`，提供后续浏览器模板、双订阅绑定和自检共同使用的持久化底座。它不更换 Gecko 内核，不移动任何现有环境目录，不重置登录，不创建伪造指纹。

## 已实现

- `ProfileCatalog` SQLite schema 6 → 7，只增加 `environment_id`。每个环境使用 UUID；升级与重复打开保留 UUID，完成删除后重新创建槽位获得新的 UUID。原来的 `generation`、删除锁和心跳代际校验继续有效。
- `EnvironmentSpec` 不可变快照。`desiredRevision`、`appliedRevision`、`observedRevision` 分别表示用户期望、运行时承认及实际观测；保存期望值不会推进其余两种状态。修改配置采用期望版本比较，过期结果不能覆盖更新后的配置。
- `EnvironmentSpecMigration` 迁移当前手机／桌面显示、兼容／标准／原生 RFP 保护、入口选择模式及已有网络绑定。桌面＋兼容、桌面＋RFP 等旧组合保持不变。迁移初始 `appliedRevision=0`，等待真实适配器应用。
- `EnvironmentSpecRepository` 使用原有每槽位 SecretStore Keystore 别名和 no-backup 目录，新增 AES-GCM + AtomicFile 的 `environment-spec.sealed`。未加密的全局目录只保留 UUID 等元数据；网络账号、密码和含令牌的订阅 URL 不复制进配置模型。
- 读取失败、认证密文损坏、身份不符、未知 schema 均报错并保留旧文件；不以空对象覆盖。仅在确实不存在新配置时进行旧设置迁移。恢复 AtomicFile 只有 `.bak` 的中断写入。
- `EnvironmentApplyCoordinator` 提供带身份／版本的 Prepared 快照和忙碌延后判定，明确分开持久化和真实浏览器操作。调用者负责实际应用及回退。
- 默认槽位删除时清理新密文及锁文件；其他槽位沿用现有完整 no-backup 清理。共享订阅库及旧密钥保留。

## API 与状态转换

```java
EnvironmentSpecRepository repository = new EnvironmentSpecRepository(profileContext);
EnvironmentSpec before = repository.load();
EnvironmentSpec.Configuration candidate = new EnvironmentSpec.Configuration(
    validatedBrowserJson, before.desired().network);
EnvironmentSpec pending = repository.updateDesired(
    before.identity, before.desiredRevision, candidate);
// 此时只保存期望配置；当前网页、登录、连接不因此改变。
```

浏览器 JSON 与 `BrowserIdentitySpec` 对齐：`schema`、`templateId`、`display`、`privacy`、`locales`、`timezoneStrategy`。模型只保存已准备的配置，适配器负责检查模板和真实 SDK 支持状态。设置语言或时区的保存动作不能代替内核生效检查。

```java
EnvironmentApplyCoordinator apply = new EnvironmentApplyCoordinator(repository);
EnvironmentApplyCoordinator.Prepared prepared = apply.prepare(currentTaskBusy);
if (prepared.deferred) {
    // 等当前任务结束，再 prepare；不得擅自中断生成、上传或下载。
    return;
}
apply.requireCurrent(prepared);
// 真实 Gecko adapter 应用并核实配置；网络层验证 route binding。
// 两者必须都对应 prepared.configuration 才可以确认完整应用。
apply.acknowledge(prepared, actualEngineVersion);
```

`appliedRevision` 对应完整配置（浏览器和网络），不能在出口尚未核验、线路绑定不一致时仅凭 `configure()` 推进。外部网络同样要遵守已有 VPN／代理门禁。应用失败仍保留旧 applied 状态；用户可以修正 desired 或经验证重新应用旧策略。

```java
repository.recordObservation(identityAtSamplingStart,
    appliedRevisionAtSamplingStart, guardedObservation);
```

记录观测还要求采集器自行验证导航 epoch、目标页面、请求关联 nonce 和采样上下文。Repository 负责身份及 applied 版本，不会把任意网页提交的 JSON 自动当成可信指纹证明。观测失败也可作为报告数据保存，表示实测结果而非能力已通过。

## 网络绑定与旧数据

`NetworkBinding` 只包含：网络方式、入口来源／节点 ID、出口来源／节点 ID、入口选择策略，以及入口配置、出口配置和凭据的修订摘要。凭据继续在 SecretStore 的原网络配置中保存。`credentialRevision` 对应路由元数据中的 `exitCredentialRevision`。

新网络配置显式提供 `entrySourceId`、`entryNodeId`、`exitSourceId`、`exitNodeId`、`entryConfigRevision`、`exitConfigRevision`、`exitCredentialRevision` 时直接迁移。旧入口使用来源 URL 的摘要及带 `legacy-entry-` 前缀的节点摘要；它表示旧的名称选择器，尚未承诺提供商真正稳定的节点身份。手工出口保留原凭据指纹 ID，`exitSourceId` 为空。

库更新时先解析和验证候选，再在既有安全应用流程中更新路由引用。更新 desired 网络绑定不会自动切换运行线路。入口或出口修订变化需要网络层使相关闲置连接失效；已经发送的健康任务依然沿用既有保护规则。

## 锁与线程

- Repository 操作顺序为本进程槽位锁 → catalog SQLite writer transaction → 环境文件锁 → sealed I/O。删除同样受 catalog writer transaction 约束，因此密文写入中途不会发生槽位删除／复用。
- 不要在 Repository／`withIdentity` 回调里调用 NetworkCatalog；其网络文件锁可能形成反向依赖。先读取网络快照，释放网络锁，再写环境配置。
- 在工作线程执行 Keystore、文件锁和迁移操作。异步返回界面时检查 Activity 生命周期、环境身份和版本。
- 不调整 `pocket-network-v1[-envN]` 的密钥命名，不重新分配数据库或 Gecko 私有目录。UUID 是新配置身份，不能替代现有存储位置。

## 验证

`tests/browser-runtime/EnvironmentSpecTest.java` 对生产模型与迁移运行了 **88 项 JVM 断言**，覆盖不可变性、版本比较、晚到应用／观测结果、损坏／未来 schema、身份和 8 槽位隐私组合迁移。它不验证 Android Keystore 或网页指纹。

示例运行（需要兼容的 `org.json` JAR）：

```sh
mkdir -p work/environment-host
javac -encoding UTF-8 -cp "$JSON_JAR" -d work/environment-host \
  app/src/main/java/local/pocketchat/J.java \
  app/src/main/java/local/pocketchat/EnvironmentSpec.java \
  app/src/main/java/local/pocketchat/EnvironmentSpecMigration.java \
  tests/browser-runtime/EnvironmentSpecTest.java
java -cp "work/environment-host:$JSON_JAR" local.pocketchat.EnvironmentSpecTest
```

另提供 `tests/gecko/EnvironmentSpecIntegrationActivity.java`，使用真实 SQLiteOpenHelper、Android Keystore、AtomicFile 和生产删除流程验证：schema 6 → 7、UUID 重启持久化、旧目录／密文保留、读取失败不覆盖、备用文件恢复、槽位删除／复用及旧异步结果拒绝。该 Activity 只允许 `.test` 包名，使用合成数据，须在独立测试安装中运行。

集成 manifest 应注册：

```xml
<activity android:name="local.pocketchat.EnvironmentSpecIntegrationActivity"
    android:exported="true" android:process=":environment_spec_fixture" />
```

```sh
adb shell am start -n local.pocketchat.test/local.pocketchat.EnvironmentSpecIntegrationActivity
adb logcat -d -s PocketEnvironmentSpec
```

当前 Android 组件及此测试已做源代码编译；本交付环境没有运行 ARM 真机／模拟器。Android 运行结果、跨进程竞争压力测试、真实登录、Service Worker 数据隔离及网页跨上下文指纹仍是合并后的发布验证项。不要把此代码包直接标为已验证正式版本。
