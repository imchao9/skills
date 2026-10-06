# Self-created skills

这个目录是本仓库自创 Skill 的 canonical source。每个子目录都是一个独立安装单元；仓库根目录不是一个需要整体安装的 Skill 包。

当前已确认的自创 Skill：

- `basketball-highlight-builder`
- `basketball-pure-cut`
- `cskill`
- `draft-internal-requirement-brief`
- `feedgrab`
- `grok-research`
- `install-codex-auth-sync`
- `tapd`
- `technical-deck-qa`
- `workflow-packaging-audit`
- `xiaohongshu-obsidian`
- `xiaoqiumi-match-review`

单独安装一个 Skill：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add \
  https://github.com/imchao9/skills/tree/main/skills/<skill-name> \
  --agent codex --copy --yes
```

从本仓库选择多个 Skill 时，在同一个 Git source 后重复传入 `--skill <skill-name>`。不要把整个仓库当成一个安装单元。

`profiles/` 负责来源分类、组合说明和运行态快照。profile 中保留的旧副本用于兼容当前运行态；自创 Skill 的新修改从这个目录开始。
