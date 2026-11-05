# Gecko HTTP 请求 UA 对齐

当前环境的内核、配置目录、Cookie、线路保护和指纹模板保持各自的真实来源。
新增扩展使用 Firefox 的阻塞式 `webRequest.onBeforeSendHeaders` 修改真实请求的
公共 HTTP(S) 请求的 `User-Agent`，来源是当前原生 `GeckoSession.getUserAgent()`，没有替换网页或
Worker 的 `navigator`、`Date`、`Intl` 等 JavaScript API。

请求类型和 `tabId` 不用来猜测 Worker：页面、脚本、fetch 以及没有普通标签 ID
的公共 HTTP(S) 请求都走同一个环境策略。公共范围由原生非虚拟的
`GeckoNavigationPolicy.publicWeb` 判定。每个环境原有独立进程和 Gecko runtime；
同一运行时的会话及弹窗本来就使用相同的 UA 模板。

## 原生来源和失败处理

- 原生桥在请求开始及实际 SDK 读回后核对会话、原生端口、配置修订、导航代次、
  原生保护 token、语言请求确认和现有线路门禁。每个请求分别核对目标授权。
- 相同原生上下文共享一次实际 SDK 读取；配置、导航、会话、保护 token 或端口
  改变后不复用旧读数。SDK 读取失败不会以旧 UA 补位；后续显式请求可以重读。
- 扩展仅接受有界 ASCII UA 和严格的当前修订回执。端口断开或配置失效立即取消
  尚未完成的请求；原生读取超过五秒也取消，没有静默沿用 Worker 默认值。
- 扩展监听器安装完成与 UA 读回分开确认。允许先创建空原生会话以获取 UA，
  避免启动互锁；监听器未安装时，原生路由不放行新的网页请求。
- 现有 `proxy.onRequest` 及原生网络守卫继续逐请求检查线路，没有新增直连回退。

内部扩展可以通过原有 URL 准入机制允许私有地址。这些地址在原有线路及目标
授权检查通过后返回明确的 `private-admission-unchanged` 回执，保留原生 SDK
原请求头，不读取或声称已对齐公共 UA；仍经过检测敏感头清理。没有测试包名、
端口或检测页面特例。正常产品的私有地址拒绝策略保持，公共网站默认启用对齐。

## 检测请求仍保持独立

原检测站的有效 nonce、范围、用途、过期、取消与重定向检查保留。
全局和检测站监听器调用同一个组合决策；对有效检测请求先清除 Cookie、
Authorization、Proxy-Authorization、Referer 和 Origin，再应用 UA。异步读取
完成后再次核对检测授权，两个监听器不会恢复已清除的敏感头。

独立扩展控制请求的 UA 不作为页面或 Worker 的 UA。只有浏览器报告的本扩展
来源、有效已注册用途和真实在途 `result` / `capabilities` 请求同时匹配时，才
保留其控制请求 UA。路径、nonce 或 `tabId=-1` 单独存在均不足以豁免。

## 观测与验收范围

`GeckoWebView.nativeRuntimeCapabilities().requestHeaderPolicy` 独立记录监听器安装、
实际公共请求原生 UA 读回及配置修订，以及内部私有准入保留原头的范围。它不是服务端收到请求头的证据；
`sharedWorkerWireVerified` 和 `serviceWorkerWireVerified` 仍为 `false`。

主机验证执行实际 Java 方法、扩展和授权过滤脚本，使用明确的 SDK、端口、
浏览器与计时器边界。它们不能代替 Android / Gecko / 服务端请求记录。
真实验收需要单独核对 Dedicated、Blob、Shared、Service Worker 的请求头，
环境切换、重启和升级安装后的脚本版本，以及门禁关闭后服务器没有新请求。

此改动不提供独立时区、硬件伪装、TLS 指纹、全部 Worker JavaScript 一致性，
也不把原生 RFP 设置回读作为全部 API 保护证明。
