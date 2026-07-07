# 语言
默认使用简体中文回复；用户明确要求时再切换。

# 项目定位
这个仓库是个人 `.agents` profile 仓库，真正的安装态放在 `profiles/<profile>/.agents/skills/`。

后续业务项目默认不要重复复制 skills，也不要走额外初始化命令；直接用软链把业务项目的 `.agents` 指向某个 profile 的 `.agents`：

```bash
ln -s /Users/cm/Documents/Me/skills/profiles/all/.agents /path/to/project/.agents
```

根目录 `.agents` 只是默认 profile 的 alias：`.agents -> profiles/all/.agents`。

# Skill 安装
外部来源使用 Vercel `skills` CLI 安装到 profile 内的 `.agents/skills/`。Git 跟踪复制后的 skill 文件；不把 `skills-lock.json` 当维护入口。

在目标 profile 目录里直接运行 Vercel CLI，不在本仓库再包一层命令：

```bash
cd /Users/cm/Documents/Me/skills/profiles/all
env -u http_proxy -u https_proxy -u all_proxy npx --yes skills@latest add <owner>/<repo> --agent codex --skill '*' --yes --copy
```

# Skill 来源标记
自研或自维护 skill 需要在 `SKILL.md` frontmatter 里标记来源，方便后续区分本地资产和外部安装包。

确定是本地创建或长期自维护时使用：

```yaml
x-provenance: local
x-owner: cm
x-source-note: created from local workflow
```

本地项目定制证据较强、但还没有确认是否完全从零创建时使用：

```yaml
x-provenance: local-candidate
x-owner: cm
x-source-note: local project-specific skill; original source not fully confirmed
```

外部 GitHub / registry 安装的 skill 不要补成本地来源；优先保留原始 `skills-lock.json`、README、LICENSE、`github:` 或评估报告里的来源证据。只有确认已经成为本地 fork / patched copy 时，才补充清楚的 `x-source-note`。

# 约束
- 默认安装到 profile 内的 `.agents/skills/`，不要装到全局 `~/.codex/skills`、`~/.agents/skills`，除非用户明确要求。
- 全局 `~/.agents` 只作为同名碰撞检查对象，不作为默认安装目标。
- 在这个仓库里安装时使用 `--copy`，因为业务项目通过 symlink 复用整个 profile 的 `.agents`。
- 不要把类型目录放进 `.agents/skills/` 下面；agent 运行时保持 `.agents/skills/<skill-name>/SKILL.md` 的扁平结构。
- 不引入 CStack 的 `role / workflow / pack / preset / doctor / sync` 体系；这个仓库只保存可被软链复用的 `.agents`。
- 不新增脚本、CLI、manifest 或 source registry；需要安装时直接跑 Vercel CLI，装完提交 Git。
- 终端命令默认通过 `rtk proxy` 执行。
- 本机代理可能影响 npm/GitHub 请求；运行 Vercel CLI 时优先临时清掉 `http_proxy`、`https_proxy`、`all_proxy`。
