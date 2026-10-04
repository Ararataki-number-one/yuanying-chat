# 1.5.11 修改说明

| 文件 | 修改与原因 |
| --- | --- |
| `AppUpdateActivity.java` | 简洁更新页：真实版本、说明、进度、取消/重试、下载偏好与安装入口；读取系统安装权限并打开原生安装器，不创建浏览器。 |
| `AppUpdates.java`、`AppUpdateJob.java` | 跨环境共用入口；每天检查与打开应用时补查，支持关闭调度；系统限制不会阻断手动检查。 |
| `AppUpdateManager.java` | 统一管理检查、系统后台下载、断网等待、取消和安装前核验；缓存新版信息、设置状态和轻通知。 |
| `AppUpdatePolicy.java`、`AppUpdateInfo.java` | 限定正式渠道、包名、版本、原签名和下载链接；限制元数据和 APK 大小，核对完整流内容。 |
| `AppUpdateFiles.java` | 用 Android PackageManager 读取实际安装包身份和签名，核对安装版本，拒绝调试或不同签名文件。 |
| `AppUpdateProvider.java` | 仅应用可控制更新；安装器只能通过显式授权读取一个已核验 APK，不能写入或读取其他数据。 |
| `AppUpdateReceiver.java` | 系统下载完成后核验已登记的下载，不信任广播声明的下载结果。 |
| `DesignSettingsUi.java` | 设置新增应用更新入口和当前可更新状态。 |
| `MainActivity.java`、`AppSettingsActivity.java`、`BrandLaunchActivity.java` | 打开应用时安排过期更新检查，不改变浏览器会话或页面。 |
| `AndroidManifest.xml`、`app/build.gradle` | 注册更新组件和安装/持久调度权限；版本 1.5.11 / code 37；测试签名可明确指定，正式版继续本机原签名。 |
| `tools/publish-update-feed.py`、`publish-gecko-release.py`、发布 workflow | 公开签名 APK 完整下载核验成功后发布更新元数据，拒绝降级和同版本替换文件。 |
| `tools/sign-apk.py` | 正式签名时同时核对新增更新测试入口和旧测试提供者不存在。 |
| `tests/browser-runtime/AppUpdatePolicyTest.java`、`tests/gecko/AppUpdateIntegrationActivity.java`、`update-fixture.xml`、`run_device.py`、构建 workflow | 23 项更新主机检查；实际系统下载、错误签名与哈希拦截、只读授权和 Android 安装器入口测试。临时测试密钥不进入正式发布。 |

[使用与架构说明](APP-UPDATES.md) · [构建、Android 与公网验证](../verification/app-updates-v1.5.11/README.md)。
