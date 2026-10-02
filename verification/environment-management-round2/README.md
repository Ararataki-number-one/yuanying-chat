# 1.5.1 环境管理与覆盖更新验证

日期：2026-10-02。最终版本 1.5.1（versionCode 27），使用用户提供的原发布密钥；APK 证书与原发布 v1.5.0 完全一致。测试环境为 Android 15 AOSP x86_64 软件模拟器、WebView 124.0.6367.219，宿主无 `/dev/kvm`，没有连接真实手机。

| 验证范围 | 结果 |
| --- | --- |
| 普通包、独立测试包构建 / 签名 / ZIP 对齐 / 包信息 | 通过 |
| 环境管理、旧目录迁移、筛选 / 多选 / 批量操作 / 路由 | 42 / 42 |
| 启动与默认环境路由 | 10 / 10 |
| 原生下载中心与已保存文件的实际提供器读取 | 5 / 5 |
| 原发布 1.5.0 覆盖到 1.5.1 | 25 / 25 |
| 上一轮原签名预览包覆盖到 1.5.1 | 25 / 25 |
| 回归检查合计 | 107 / 107 |
| WebView 界面、真实账号登录 / 发送 / 网络下载 | 未完成 / 未验证 |

共享环境目录分别检查历史 v1 的连续迁移、原发布目录 v3 升至 v4、上一轮目录 v4 的原样保留。环境管理回归发现并修复了批量分组弹窗的确认按钮初始化时序；最终包重跑全部 42 项通过。

覆盖更新用独立、同证书的 instrumentation APK 运行在实际已安装的发布包内：先安装各基线包，使用应用自己的实现保存样本 Cookie、环境资料、配置草稿、偏好、会话草稿、消息缓存、加密记录和已保存文件，再执行 `adb install -r`。更新期间没有卸载或清除基线数据。检查 Android UID 保持、真实 WebView Cookie 保留、两环境的加密记录继续解密、已保存文件通过正式提供器读取、文件索引、默认环境和启动模式保留。两个独立用例之间重置一次性模拟器里的基线应用，工具禁止用于真实手机。

本轮测试包安装后核对 versionCode 27，结果只统计最终测试包的当前 JSON。构建产物哈希和检查数量见 [summary.json](summary.json)，逐项结果见本目录 JSON。原版密钥留在忽略目录，未包含在源码或发布附件。

含 WebView 的 `DesignUiTestActivity` 没有生成当前结果，模拟器出现 Android 系统服务 ANR。[取证截图](emulator-anr.png) 展示模拟器 System UI 无响应，背景为覆盖更新样本环境。会话连续性、网页草稿冲突和下载传输回归因此未继续执行，没有将历史成绩计入。样本 Cookie 的保留只验证本地登录存储，不代表网站仍接受真实账号会话。真实手机及网站行为按 [手机复核清单](DEVICE-CHECKLIST.md) 补齐，待验证项目见 [pending-checks.json](pending-checks.json)。

## 重跑

使用最终独立测试包，在每个测试前停止 `local.pocketchat.test` 并删除对应旧结果，分别启动 `WindowHomeTestActivity`、`DesignLaunchTestActivity`、`DownloadCenterTestActivity`；通过 `adb exec-out run-as local.pocketchat.test cat files/<结果名>` 读取新 JSON。测试原签名升级见 [覆盖更新工具](../../tests/upgrade/README.md)。不要将不存在、没有检查项、含错误或有失败项的结果算作通过。
