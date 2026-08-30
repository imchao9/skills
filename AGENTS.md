# 语言
默认使用简体中文回复；用户明确要求时再切换。

# 项目定位
这个仓库是个人 `.agents` profile 仓库，真正的安装态放在 `profiles/<profile>/.agents/skills/`。

后续业务项目默认不要手工复制 skills，也不要直接依赖本机路径；应从本仓库的 GitHub source 安装对应 profile：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/core \
  --agent codex --skill '*' --yes --copy --full-depth
```

Git source 只包含已经提交并推送到 GitHub 的内容。
本地路径安装只用于未推送内容验证。
软链只用于同机共研且需要实时跟随 canonical profile 的项目；优先只链接
`.agents/skills`，替换前检查差异和 Git 状态并保留原目录备份。
长期业务、CI、远程部署和跨机器项目继续使用 Git source `--copy`，绝对软链不提交。
profile 之间不以软链代替来源审查和晋级同步。
根目录 `.agents` 只是默认 profile 的 alias：`.agents -> profiles/core/.agents`。

# Profile 语义
- `profiles/core`：默认最小集，只放稳定自研或长期自维护 skill。
- `profiles/global-runtime`：本机 `~/.agents/skills` 的真相源，只放当前全局可用的稳定 skill。
- `profiles/ppt`：正式 PPT / HTML 演示稿生产链路；实验候选放 `profiles/ppt-lab`。
- `profiles/web`：正式联网入口，目前只保留 `agent-reach`；其它抓取/浏览器实现放 `profiles/web-lab`。
- `profiles/basketball`：篮球视频专用 skill，包括纯享版剪辑和集锦生成。
- `profiles/mattpocock-skills`：来自 `mattpocock/skills` 的外部 skill，保留 GitHub 仓库名以区分来源。
- `profiles/codemao`：公司 GitLab 内源 skill，先评估再挑选稳定项进入全局运行态。
- `profiles/vendor-lab`：EveryInc、GitHub 大佬和其它开源 vendor 候选，试用稳定前不要进入全局运行态。
- `profiles/rtk-candidates`：RTK 本地候选 skill，未确认长期保留前不要放进 `core`。
- `profiles/experimental`：其它实验或待归类 skill。
- 不再使用 `profiles/all`，避免把“默认集”变成所有东西的混装目录。

# Skill 安装
外部来源使用 Vercel `skills` CLI 安装到 profile 内的 `.agents/skills/`。
Git 跟踪复制后的 skill 文件；不把 `skills-lock.json` 当本仓库维护入口。
但外部或公司来源 profile 必须保留 profile 级 `skills-lock.json` 作为来源清单，例如 `profiles/mattpocock-skills`、`profiles/codemao`、`profiles/vendor-lab` 和 `profiles/experimental`。
其它业务项目应从 `imchao9/skills/profiles/<profile>` 这个 Git source 安装，目标项目自己的 `skills-lock.json` 记录 Git 来源。

在目标 profile 目录里直接运行 Vercel CLI，不在本仓库再包一层命令：

```bash
cd /Users/cm/Documents/Me/skills/profiles/<profile>
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
- 默认安装到 profile 内的 `.agents/skills/`，不要装到全局 `~/.codex/skills`。
- 全局 `~/.agents/skills` 由 `profiles/global-runtime/.agents/skills` 生成或软链提供，不要手改。
- 在这个仓库里安装时使用 `--copy`，因为本仓库直接跟踪安装后的 skill 文件。
- 不要把类型目录放进 `.agents/skills/` 下面；agent 运行时保持 `.agents/skills/<skill-name>/SKILL.md` 的扁平结构。
- 不引入 CStack 的 `role / workflow / pack / preset / doctor / sync` 体系；这个仓库只保存可被 Git source 安装复用的 `.agents`。
- 不新增脚本、CLI、manifest 或 source registry；需要安装时直接跑 Vercel CLI，装完提交 Git。
- 本机代理可能影响 npm/GitHub 请求；运行 Vercel CLI 时优先临时清掉 `http_proxy`、`https_proxy`、`all_proxy`。
