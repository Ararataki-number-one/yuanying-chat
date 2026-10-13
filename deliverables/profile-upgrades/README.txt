PocketChat 1.6 → 1.7 → 2.0 候选源码交付

基于正式 v1.5.21-gecko，未合并主分支、未发布 APK。
在干净分支执行：
  git switch -c review/profile-upgrades v1.5.21-gecko
  git am /交付目录/patches/1.6.0.patch
  git am /交付目录/patches/1.7.0.patch
  git am /交付目录/patches/2.0.0.patch
有你自己的修改时先审查冲突，保留原签名和数据目录。

source-delta 是三个版本累计变更的源码和文档，补丁保留完整差异与提交。
逐版范围、剩余工作、运行方法见 source-delta/docs/IMPLEMENTATION-*.md
及 MERGE-AND-ACCEPTANCE.md。verification 是限定范围的主机检查，
不能代替完整 APK、官方 SDK、Android/ARM 真机或真实 Google 登录验收。

2.0 为官方 SDK 阶段：资源保护、能力清单和维护框架；独立原生时区及
Canvas/WebGL/音频/字体自定义仍待实现与真机验证，没有伪装成已完成。
