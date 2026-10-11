应用更新位于“设置 → 应用更新”。默认自动检查打开，Wi-Fi 自动下载关闭，手动下载只使用 Wi-Fi。安装 1.5.11 后，后续正式版可在应用中发现。

从 1.5.19 起，更新页提供下载进度、实际传输速度、预计剩余时间、暂停、继续和安装按钮。下载由独立传输线程与 Android JobScheduler 管理，退出更新页仍可继续；网络中断或系统停止任务时保留已下载部分，恢复后请求剩余字节。手动暂停会保留进度；“取消下载”会明确删除进度，并禁止自动重下同一个版本。进度刷新只更新现有控件，不每秒重建整个页面。

部分文件与版本号、SHA-256、文件大小绑定，续传只使用官方 GitHub Release HTTPS 地址，每次重新获取 CDN 跳转。服务器返回的范围、大小和强 ETag 必须一致；服务器不支持续传而返回完整文件时，从零正确重下，避免把两份内容拼在一起。自动下载仍只在非计费网络执行；手动下载可按用户的 Wi-Fi 偏好执行。安装本版前已由 DownloadManager 开始的旧任务继续按原方式核验完成。

自动检查通过 JobScheduler 每 24 小时请求一次，也会在打开应用时补做过期检查；成功检查间隔为 24 小时，失败后最早 6 小时重试。省电或后台限制可能延后执行。关闭自动检查会取消定期和打开应用的检查任务，手动检查不受影响。

更新任务在默认应用进程统一管理，独立环境通过私有 ContentProvider 查询同一状态；不建立 WebView，不操作会话、不更新浏览器网络设置。传输使用手机网络或 VPN，更新请求不携带网页登录凭据。

发现渠道为固定的 HTTPS 地址：

`https://raw.githubusercontent.com/Ararataki-number-one/yuanying-chat/app-updates/latest.json`

元数据限定 schema、正式包名、ARM64、最低 Android 版本、原版证书和固定 GitHub Release 下载路径。正式发布工具先验证签名、安装包和已通过的测试记录，再匿名完整下载公开 APK，核对字节数和 SHA-256，最后推动 `app-updates` 分支；渠道拒绝降级和同版本替换文件。发布流程没有依赖 GitHub API 来发现更新。

客户端下载先在应用私有目录保存部分文件，再复制成完整候选文件，在复制过程中核对大小与 SHA-256，随后读取 APK 的包名、版本、系统要求和签名，并与已安装应用核对。失败文件不会得到安装 URI。安装前再次核验，提供给安装器的 URI 只可读单个已核验 APK，不能读取环境文件或写回。

普通 Android 应用无法静默覆盖安装。点击“安装更新”后先检查系统“安装未知应用”权限，必要时引导打开本应用的权限页面；返回后由 Android 安装器确认覆盖安装。用户可以取消安装，已经下载的安装包保留供以后安装。真正覆盖安装会由 Android 结束并替换旧应用进程；账号数据没有被应用清除。

控制更新的来源文件见 `AppUpdates`、`AppUpdateManager`、`AppUpdateTransfer`、`AppUpdateActivity`、`AppUpdateProvider`、`AppUpdateFiles`、`AppUpdatePolicy`、`AppUpdateJob` 和 `AppUpdateReceiver`。`tools/publish-update-feed.py` 维护公网渠道。测试只用合成 APK，原签名密钥不进入 CI 或公网。

发布时，`docs/RELEASE-v版本.md` 用作应用内用户可读的简短更新说明；实现细节和验证限制写入 CHANGELOG 与 verification 文档，避免技术字段挤占更新页。
