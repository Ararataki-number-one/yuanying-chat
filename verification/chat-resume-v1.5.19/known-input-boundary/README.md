# 偶发硬件按键光标回退 · 尚未归因

这是独立的未解决问题记录，不是本版的通过验收。此前正常回归 source 472b7b3 在单次 Android 硬件按键输入中，e 后光标从 26 回到 25，导致完整 marker 错位；同样现象也曾在 6e6086f 出现。原报告、分析、源码和不可变 artifact SHA 保留，可核查输入完整顺序以及没有自动重试。

[原正常失败](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38161004986)与[原生诊断](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/38162595457)分别保存。三次原生诊断全部通过并不解释失败；没有观察到失败时的真实写入者。5fd 与 472 的生产输入代码相同，SDK 未修改，未经验证的 SDK 实验补丁未加入正式包。本版最终正常回归仅代表该轮未复现，不证明偶发问题已修复，也不是用户真机软键盘测试结论。
