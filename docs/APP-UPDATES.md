应用更新位于“设置 → 应用更新”。默认自动检查打开，Wi-Fi 自动下载关闭，手动下载只使用 Wi-Fi。安装 1.5.11 后，后续正式版可在应用中发现。

更新页提供版本说明、下载进度、取消、重试和安装按钮。下载留给 Android DownloadManager 处理，退出更新页仍可继续；网络不满足条件时会等待，恢复网络后由系统继续。取消后不会自动重下同一个版本，用户可以手动重新下载。

自动检查通过 JobScheduler 每 24 小时请求一次，也会在打开应用时补做过期检查；成功检查间隔为 24 小时，失败后最早 6 小时重试。省电或后台限制可能延后执行。关闭自动检查会取消定期和打开应用的检查任务，手动检查不受影响。

更新任务在默认应用进程统一管理，独立环境通过私有 ContentProvider 查询同一状态；不建立 WebView，不操作会话、不更新浏览器网络设置。传输使用手机网络或 VPN，更新请求不携带网页登录凭据。

发现渠道为固定的 HTTPS 地址：

`https://raw.githubusercontent.com/Ararataki-number-one/yuanying-chat/app-updates/latest.json`

元数据限定 schema、正式包名、ARM64、最低 Android 版本、原版证书和固定 GitHub Release 下载路径。正式发布工具先验证签名、安装包和已通过的测试记录，再匿名完整下载公开 APK，核对字节数和 SHA-256，最后推动 `app-updates` 分支；渠道拒绝降级和同版本替换文件。发布流程没有依赖 GitHub API 来发现更新。

客户端下载先由系统完成，再将内容复制到应用私有目录，在复制过程中核对大小与 SHA-256，随后读取 APK 的包名、版本、系统要求和签名，并与已安装应用核对。失败文件不会得到安装 URI。安装前再次核验，提供给安装器的 URI 只可读单个已核验 APK，不能读取环境文件或写回。

普通 Android 应用无法静默覆盖安装。点击“安装更新”后先检查系统“安装未知应用”权限，必要时引导打开本应用的权限页面；返回后由 Android 安装器确认覆盖安装。用户可以取消安装，已经下载的安装包保留供以后安装。真正覆盖安装会由 Android 结束并替换旧应用进程；账号数据没有被应用清除。

控制更新的来源文件见 `AppUpdates`、`AppUpdateManager`、`AppUpdateActivity`、`AppUpdateProvider`、`AppUpdateFiles`、`AppUpdatePolicy`、`AppUpdateJob` 和 `AppUpdateReceiver`。`tools/publish-update-feed.py` 维护公网渠道。测试只用合成 APK，原签名密钥不进入 CI 或公网。
