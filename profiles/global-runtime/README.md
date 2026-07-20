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

外部来源 skill 的 canonical source、本地 fork 和升级策略记录在 `UPSTREAM.md`。
更新运行态前先查看该文件，不要把来源 profile 整体盲目覆盖到这里。

公司 GitLab skill 当前从以下来源安装：

```text
git@gitlab.codemao.cn:backend/platform-informatization/tool/skills.git
```

安装后必须清理 `data/`、`output/`、JSONL 历史结果和 Python 缓存等运行产物。

`~/.agents/plugins` 和 `~/.agents/.skill-lock.json` 不属于这个 profile。
它们仍保留在 `~/.agents` 下，由 Codex plugin marketplace 和 `skills` CLI 管理。
