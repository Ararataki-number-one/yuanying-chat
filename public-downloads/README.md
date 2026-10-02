# 1.5.2 交互与页面整理预览版（原版签名）

版本 1.5.2（versionCode 28），更新日期 2026-10-02。

## 下载与覆盖安装

[下载 APK](https://raw.githubusercontent.com/Ararataki-number-one/yuanying-chat/refs/heads/apk/environment-management-preview-20261002/public-downloads/PocketChat-1.5.2-interaction-preview.apk)，49,341,806 字节。

SHA-256：`d5d537185ef757bd557d8eec04cbe00ea158d850a15e07a7e4c91c5a5efc253d`。

使用原发布签名，包名保持 `local.pocketchat`，可覆盖安装原签名版本。此前临时签名预览包不适用。此次核对签名与版本号，未重新执行覆盖更新回归。

## 页面变化

- 聊天顶部合成一行，环境名称、网站和主要操作直接可见。正常连接时隐藏网络状态条。
- 环境列表压缩卡片，把分组和排序放入筛选，备注放入详情。
- 网络页突出连接状态和主要操作，仅展示当前网络方式适用的分页。
- 浏览器参数、日志、存储位置等低频信息点开查看，减少常驻说明和重复卡片。
- 统一返回、表单错误、加载和空列表行为，保留填写内容与刷新前的滚动位置。

## 验证范围

release 与 test APK 构建、签名、对齐和版本检查通过。66 项原生管理页检查通过（环境管理 48、启动设置 10、下载中心 8）。这些检查使用聊天顶部最后一次调整前的测试包；原生管理页组件此后没有修改。

最终测试包的 WebView 界面回归等待 150 秒后仍未生成结果，记为未完成；模拟器出现系统 UI 无响应。没有连接真机，真实账号登录、发送、网页草稿和网络下载仍需手机验证。详细记录见 `verification/interaction-round3/`。

源码提交：`4ed0d9726c2e6b9c9b0e2cdb8fb49607cd425199`，源码分支：`release/interaction-v1.5.2`。

原签名的 1.5.0、1.5.1 预览包保留在此目录。通过 GitHub 下载分支发布，签名密钥没有放入源码或下载文件。
