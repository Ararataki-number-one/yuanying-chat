PocketChat 1.6 → 1.7 → 2.0 候选源码交付

基线 v1.5.23-gecko，源码 6a1bab77f1bcc70f0fc4f990b287fec08ec54412；未合并主分支、未发布 APK。
在干净分支执行：
  git switch -c review/profile-upgrades v1.5.23-gecko
  git am /交付目录/patches/1.6.0.patch
  git am /交付目录/patches/1.7.0.patch
  git am /交付目录/patches/2.0.0.patch

补丁按顺序应用，source-delta 是累计源码变更。请审查各版本实施和合并验收说明。
verification 只包含绑定本包源码提交的主机报告，不代替官方 SDK 完整构建、
Android/ARM 真机、真实登录、网页指纹或网络性能验收。
2.0 仍使用官方 GeckoView：深层独立时区、Canvas/WebGL/音频/字体自定义
原生控制未实现；可选原型证据和资源预算不会自动启用后端。
请保留原签名和数据目录；升级 versionCode 必须高于已发布/安装版本。
重新导出必须使用新目录，不覆盖或混入旧包。

此包替换此前基于1.5.21的旧候选包。保留1.5.23已发布的双订阅、快照、安全应用、缩放和键盘修正。此delivery分支只存放交付物；代码审查使用三个候选分支，不要合并delivery分支。

三个最终候选的GitHub只读host和官方SDK release/integration APK编译、lint检查全部通过：
1.6 https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38347045296
1.7 https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38347445766
2.0 https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38347446507

验证包中同时记录仍未执行的ARM、Android/Keystore、真实登录、跨上下文指纹、公网延迟与耗电验收，以及原网页自主上传状态覆盖不足。源码修复不能承诺实际网络延迟会降低多少。

详细复查报告：
https://github.com/Ararataki-number-one/yuanying-chat/blob/codex/v2.0-maintenance-capabilities/docs/RECHECK-v1.5.23.md
