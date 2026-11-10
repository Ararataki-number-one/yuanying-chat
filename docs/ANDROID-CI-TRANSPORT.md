# Android 发布测试连接

产品仍使用单 GeckoView、各环境独立存储与固定出口。以下只描述临时 CI 模拟器的连接准备，不改变应用或输入驱动。

在 API 35 r09 的 VSOCK 路径上，实际安装 APK 的读取曾出现中途断开；固定模拟器 36.3.10、ADB 35.0.2 和分段读取均没有单独消除问题。失败保留为失败，不以诊断成功、后续光标成功或别次构建替代缺失的字节校验。

原生 TCP 的准备还暴露了独立的网络时序问题：首次 SDK 设置程序拥有最初的 Wi-Fi 请求。停用它后，即使即时 ConnectivityManager 快照健康，Wi-Fi 地址也可能随后消失。历史准备器因此改为确认 `virtio-wifi` 上的 `10.0.2.16` 源地址返回路由，再创建 Wi-Fi 原生 TCP。原来的 `prepare_native_adb.py` 与 `prepare_emulator.py` 保留，旧 Wi-Fi 用例及其源码固定值不变。

在 [42785015571 / attempt 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/42785015571) 中，原始编辑日志记录了 Wi-Fi 断开、ADB 离线和应用默认网络变化；原始 UI 截图日志记录了 Wi-Fi 断开、TCP socket 撤销和 UiAutomation owner 退出。编辑的普通性能组与 UI 的原始截图命令因此失败，该次构建没有获得发布资格。独立编辑组通过、后续重新连接或另一次截图成功均不能替代失败门槛。

完整发布流程显式选择新的 `prepare_cellular_adb.py` 入口，仅准备本次全新合成模拟器已有的移动数据网络：

1. 读取固定目标的真实 QEMU 标志、原有输入设置及带新 nonce 的实际 CM 观察；核验本次源码、SDK 与安装 APK 身份。初始 CM 必须有稳定的 `INTERNET` 网络，允许是初始 Wi-Fi；不通过启用 Wi-Fi、修改 mobile data 或切换飞行模式补救。
2. 完成原 SDK 设置包的停用和读回后，必须观察到真实、稳定、仅含 `cellular` transport 的默认网络。SDK 包停用后的切换期可以暂时没有默认网络：仅在本次停用已经确认、原身份/JSON/nonce 校验全部成功、前后网络 ID 及 capabilities 都为空、全部能力和可用性布尔值均为 `false`、transport 精确为空列表时，允许在原准备截止时间内继续只读观察。每次使用新 nonce，原空状态保留为不可用，不能计作通过；非空 Wi-Fi/VPN/混合 transport、格式/身份错误、命令失败或超时立即停止。首次真实 cellular 网络就绪后最多一次关闭 Wi-Fi，读回关闭状态与 `wlan0` IPv4 撤销，并使用另一新 nonce 直接确认同一个 cellular 网络仍有 `INTERNET`；该最终确认不等待或重试。缺少两次相邻的严格 cellular 证明就停止，不能回退 Wi-Fi 后继续。
3. 对需要原生 TCP 的三类作业，在 `emulator-5556` 启动通道上核验实际 `eth0` 地址 `10.0.2.15`，读取 `ip -4 route get 10.0.2.2 from 10.0.2.15`，并核验真实 QEMU `mynet` user backend。创建唯一的 `127.0.0.1:5555 → 10.0.2.15:5555` 转发；已有冲突转发直接拒绝。
4. 只调用一次 `tcpip`，保留原 CNXN header 探测、单向注册通知和真实 `emulator-5554 get-state` 就绪检查。切换后不再向启动通道发命令。浏览器与 TLS 作业保留原来的 `-port 5554` 启动和 ADB 通道，仅选择同一严格 cellular 前置检查。
5. 所有正式用例仍针对 `emulator-5554`，继续运行原来的 APK 字节、ZIP/DEX、SDK、源码、IME、启动器和输入断言。新准备器复用原有身份与 CM 读取、有限命令执行及原生协议检查，不运行会重新启用 Wi-Fi 的旧准备分支。

新入口不延长原准备预算：native 准备为 45 秒，源地址返回路由最多 30 秒，普通命令最多 8 秒；CNXN endpoint 检查为 8 秒，native device 就绪最多 30 秒。normal 准备仍为总计 45 秒，其中保留原 12 秒诊断时间。工作负载中的输入、断言、reader、时限与采样次数保持不变。

在 [42800077619 / attempt 1](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/42800077619) 中，profiles 与 files 的原始准备记录都显示：最初是可用 Wi-Fi；SDK 包确认停用后第一次实际 CM 读取返回完整合法的空默认网络，ADB 命令成功、身份正确，但网络尚不可用。两项作业因此在调用任何应用工作负载之前失败。当时原准备预算仍各剩约 39 秒。这些失败只支持在既有预算内等待严格验证过的空网络切换，不能证明网络后来一定恢复，也不为该构建授予发布资格。

`host:emulator` 是单向注册通知，不返回普通服务的 `OKAY`。实现依照 [AOSP 的通知测试](https://github.com/mirror/platform_packages_modules_adb/blob/1cf2f017d312f73b3dc53bda85ef2610e35a80e9/test_adb.py) 发送帧后关闭，再用真实 `get-state` 确认设备就绪。先前误加的 `OKAY` 判断使 eb927 构建的七个设备在启动阶段停止，未运行输入用例；该失败保留为失败，后续使用新源码重新构建。

独立诊断 [39923380038](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/39923380038) 在全新实例上比较默认转发和显式 Wi-Fi 转发，每个实例预先规定 64 次完整实际安装 APK 读取；诊断结果不授予应用验收。三个默认转发实例均实际记录了 `mynet → 10.0.2.15`，且分别通过 64 次大小、SHA256 和定义检查。另一组 [39942737900](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/39942737900) 设置阶段故障实验主动关闭 mobile data，随后观察到 cellular 默认网络缺失；新入口必须拒绝这种状态，不能将仍存在的地址视为可用网络。

这些历史诊断只支持准备路径的选择，不证明新入口或新版本已经通过。正式发布仍须同一最终源码、构建和尝试的全部 13 项作业、三组原始输入工作负载及最终证据门槛通过。

没有重放原始输入用例、放宽断言或时限、重读失败的 APK 分段、以编译产物替代设备字节、改动认证/防火墙或收集包内容。模拟器通过不等于真机、百度输入法或真实 ChatGPT 账号上传通过。
