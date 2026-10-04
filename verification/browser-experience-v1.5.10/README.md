# 1.5.10 Firefox 使用体验修复验证

源码：`ac4e876f319ae450f0249914303203b0742bab11`。正式包：`local.pocketchat`，1.5.10 / code 36。

[完整 release / integration 编译、Lint Vital 与 Android 回归](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/37168151087)通过。67 项主机检查通过；Android 15 / API 35、x86_64 实际执行 62 次受控操作。测试使用生产浏览器接入代码与合成数据，正式 APK 不包含测试入口或 HTTP 例外。

新增实际浏览器验证：手机版 Firefox 身份与可见页面；当前 Firefox 本机自检取得实际页面 UA、不导航到另一个页面；可信屏幕点击文件输入框，读取没有 `_data` 文件路径的系统内容提供者，网页获得 `sample.txt:synthetic-upload`；可信点击下载 CSV 和原网页创建的 Blob，均通过 Gecko 原生响应返回准确 CSV 内容；下载前后的页面地址和导航代数不变，仍可操作原网页，且未误报加载失败。

原有会话 Cookie 恢复、退出登录后不恢复、环境隔离、两个实际进程、HTTP / SOCKS 线路、窗口与历史、60%～130% 原生缩放、横竖屏、表单与原生输入、后台返回、显式清理、网络阻断、系统内核回退等回归继续通过。逐项结果见 `device-results.json` 和 `device-native-events.txt`。

源码还修复了有真实 DOM 内容时不显示整页错误遮罩、编辑取消返回环境列表、启动/关于/诊断版本统一。环境列表返回行为与真实官网白屏仍需用户真机验收，不能把受控手机版渲染通过说成已经验证 ChatGPT 账号页面。自检中受 CSP 限制的 iframe/Worker 标为未覆盖；本机检查不访问 IP 检测服务，网络检查仍需明确本次授权。

原签名 APK：`PocketChat-1.5.10-gecko-arm64.apk`，120421617 字节，SHA-256：`c7f38bb5ef968b0a3beb05d4ef726e99608b56cd6a16f60c2b87e812139ed639`。证书：`f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434`。非调试、无测试入口、16 KB ZIP 对齐；原密钥未上传。公网匿名完整下载字节与哈希已核对。

[下载 1.5.10 正式 APK（ARM64）](https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.10-gecko/PocketChat-1.5.10-gecko-arm64.apk)。

尚未验证：真实 Google / ChatGPT 账号、ARM 真机覆盖安装、实际系统内存回收、真实订阅线路、中文输入法与长期连续使用。附件验证采用受控网页的真实 file input，下载验证采用实际 Gecko 响应；并不声称已在真实 ChatGPT 中上传或下载成功。客户端无法延长服务端登录有效期。
