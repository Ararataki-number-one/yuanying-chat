# Android 预编译浏览器 SDK 实验

使用 Mozilla 官方 GeckoView 发布版 `157.0.20260924084938`。独立项目、独立包名 `local.pocketchat.engineprobe`，不引入原应用 WebView，也不读取原应用 Cookie、订阅或私钥。正式应用仍为 1.5.6；插件和网络功能开发继续暂停。

该实验不是登录修复版。Google / ChatGPT 登录必须在可信线路和真机完成验收；本包目前只开放合成数据的 loopback 测试站点，禁止进入真实账号网页。不会通过伪造 Chrome、关闭 TLS 验证或转移 Cookie 宣称修复。

## 本轮实际验证范围

- 官方 AAR 下载、SHA256、真实 SDK 接口与完整 Android 服务清单。
- APK 编译、分别生成 ARM64 和 x86_64 产物，避免把所有 ABI 装进手机。
- 同一 GeckoRuntime 中两个 `contextId` 的 Cookie、localStorage、IndexedDB、CacheStorage、Service Worker 隔离；删除一个、进程重启后检查另一个。
- 固定的实验 SOCKS5 线路：重定向、远程域名、WebSocket、专用 worker 和 Service Worker；关闭代理后检查是否意外直连。
- 记录 `proxy.onRequest` 实际提供的 `tabId` / `cookieStoreId`。**全局代理通过不代表每环境代理通过，也不代表复用了正式应用线路。**

SDK 官方 AAR 全架构下载约 242 MB，是 SDK 下载大小，不是单架构 APK 大小。许可证 MPL-2.0；原 SDK 文件不提交 Git。锁定信息见 [sdk-lock.json](sdk-lock.json)。

## 构建与执行

JDK 17、Gradle 9.8.0、Android 平台 37.1、AGP 9.4.1；生产项目原有 SDK 35 工具链保持。Google、Maven Central 和 Mozilla Maven 必须可访问。云环境代理应通过 Gradle 的 `https.proxyHost` / `https.proxyPort` 配置，不硬编码个人代理凭证。

```sh
gradle -p engine-probe :app:assembleDebug --console=plain
adb install engine-probe/app/build/outputs/apk/debug/app-x86_64-debug.apk
python3 engine-probe/tests/run_device.py --adb "$(command -v adb)" --serial emulator-5554
```

`run_device.py` 启动合成 HTTP 和 SOCKS 服务，并使用 `adb reverse` 连接。它只清空**实验包**的数据，输出新结果到忽略目录 `work/gecko-sdk-validation/`，不使用旧结果充当本次通过。调试 APK 与原版包名和签名分开，不能覆盖正式应用。

CI [engine-probe.yml](../.github/workflows/engine-probe.yml) 使用校验过的 Gradle / GeckoView 归档，构建后运行 Android 模拟器。失败也发布结果清单，缺少 `device-results.json` 表示未执行设备测试。实验产物发布到单独 `apk/gecko-sdk-probe-20261003` 分支，不改变 main 和正式 APK 下载分支。

## 当前架构判断

真实 SDK 内 `getCookieStoreIdForOriginAttributes` 只处理 `privateBrowsingId` / `userContextId`，没有处理 Gecko 的 `geckoViewSessionContextId`。所以不能把 `proxy.onRequest.cookieStoreId` 直接当作本项目的环境标识。仅按 tabId 路由也不足以证明后台 worker、DNS、下载正确隔离。

正式迁移必须额外验证每环境独立 runtime / profile / 子进程，或找到提供正确环境路由标识的成熟 SDK 接口。实验全局代理使用 SDK 配置文件和受控内置扩展，不新增用户插件；该配置文件被上游描述为调试接口，不能作为生产代理已支持的证据。

下一道门槛是复用现有环境代理后检查全部请求，并在 ARM64 真机完成 Google → ChatGPT 登录。达标之前不替换正式浏览器或搬运旧登录数据。
