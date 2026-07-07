# Global Runtime Profile

这个 profile 是本机 `~/.agents/skills` 的真相源。

当前软链关系：

```text
~/.agents/skills -> /Users/cm/Documents/Me/skills/profiles/global-runtime/.agents/skills
```

这里放当前全局可用、稳定启用的 skill。
不要把实验候选、一次性项目 skill、或还没评估过的外部仓库直接放进这里。

新增来源时先进入更具体的 profile 或 `experimental`。
确认长期复用后，再同步到 `global-runtime`。

`~/.agents/plugins` 和 `~/.agents/.skill-lock.json` 不属于这个 profile。
它们仍保留在 `~/.agents` 下，由 Codex plugin marketplace 和 `skills` CLI 管理。
