# Vendor Lab Profile

第三方 GitHub 大佬、开源项目、vendor skill 的试用区。

EveryInc、个人开源仓库和其它非公司来源的候选 skill 先进入这里或更具体的专业 lab profile。

这里不是默认运行态，也不直接等同于全局可用。

进入 `profiles/global-runtime` 前，需要至少跑过一个真实 case，并确认触发范围不会污染日常任务。

当前候选：

- `video-shotcraft`：完整保留的外部 vendor skill。
- `wechat-channels-download`：本地安全编排 wrapper，依赖 `ltaoo/wx_channels_download`，不内置上游二进制、证书或私钥；默认禁止隐式触发。
