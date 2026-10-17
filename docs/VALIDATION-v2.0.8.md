# 2.0.8 正式版验证记录

发布日期：2026-10-17（UTC）。按用户“继续，然后发布新版本”的明确指令发布。ARM 真机、真实 ChatGPT 登录及用户公网延迟没有新增验收结果。

## 源码与安装包

- 应用与发布工具源码：`d763297fd10e933b1bd5fe2880db3d19e9b092e2`。
- 冻结 Android 构建和验证产物：`ba7fe28dde56e14021795ebef7faa9c5537b2d19`。
- 正式发布产物：`39cdde12c80d20895eeda06d61db41ae5f47e247`。
- 包名 `local.pocketchat`，版本 `2.0.8`，versionCode `61`，ARM64。
- 文件 `PocketChat-2.0.8-gecko-arm64.apk`，119115144 字节。
- APK SHA-256：`6efc03c0292a7f060694e77efc47e099f3a07d144e64bfe7711d9d338eaee6fa`。
- 原签名证书 SHA-256：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`，可覆盖安装原签名应用。

## 已通过

- [构建、lint 与主机回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/39014906236)。
- [实际 Android 模拟器回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/39014906253)。
- [网络内核独立重建与原生测试](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/39014906344)。
- [正式发布工作流](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/39017571065)。
- 发布前核对源码、构建身份、原签名与实际 APK 字节；五组发布门槛、15 份 Android 报告和四份订阅主机报告通过。
- 上传、下载、恢复、环境隔离、输入、日夜模式、网络分享、反馈和连接池的既有受控回归通过。
- 公网完整下载校验与本地签名产物完全一致；发布清单一致。
- 两次 HTTP Range 下载均返回 206，If-Range 继续使用同一个强 ETag，分段字节与签名包匹配。
- 应用更新 feed 已指向 2.0.8 / code 61，GitHub latest 正确。

## 回归中发现的问题与修复

首次 Android run `39008214906` 因测试报告在后台序列化时发生并发修改而失败，没有发布该次安装包。测试夹具随后在浏览器销毁前固定完整报告，再异步写盘；没有放宽验证条件。第二次运行 `39011178278` 的中文组合输入报告也未通过；继续定位并通过受控线程屏障复现回执处理期间提前清空队列的问题。pocket2 SDK 将动作保留到处理完成，期间追加或重置后的新动作不会被误删。第三次运行 `39012796945` 的输入和网络场景通过，但阅读检查仍失败；失败截图显示页面已绘制，旧报告缺少测量值，不能仅凭截图认定原因。检查随后改用实际绘制矩阵衡量物理宽度，并保留完整失败测量；没有调整产品缩放行为或放宽宽度限制。上述通过结果来自最终完整重新运行。

## 本版重构与性能范围

公共摘要复用、订阅快照事务写入复用和下载排序字段复用；环境节点池采用集合去重，原配置身份及排序规则保留。另修复 Gecko 输入回执与文本同步之间的竞争窗口，并通过原编辑场景验收。没有修改登录目录、密钥、网页 UI、网络连接实现或提醒策略。

第一批重构的旧版对照、主机微基准和源码摘要见 [详细记录](REFACTOR-2026-10-17.md)。额外的集合去重通过环境配置迁移回归。局部 JVM 计时不等于手机整机性能；本版不宣称公网延迟达到 200 ms。

## 下载

[正式 APK](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v2.0.8-gecko/PocketChat-2.0.8-gecko-arm64.apk) · [发布页](https://github.com/Ararataki-number-one/yuanying-chat/releases/tag/v2.0.8-gecko)
