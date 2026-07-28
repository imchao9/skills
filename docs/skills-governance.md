# Skills Governance

本文固定个人 skills 的来源分层、晋级规则和全局运行态维护方式。

目标是避免把 GitHub 仓库、公司 GitLab 仓库、Codex plugins 和本地自维护 skill 混成一个不可追踪的全局目录。

## 三层模型

第一层是 `~/.agents/skills`。
这是运行态，只放当前全局可用的稳定 skill。
它不手改，当前软链到 `/Users/cm/Documents/Me/skills/profiles/global-runtime/.agents/skills`。

第二层是 `/Users/cm/Documents/Me/skills/profiles/*/.agents/skills`。
这是个人真相源，按用途、来源和成熟度分 profile。
Git 跟踪复制后的 skill 文件，升级靠重新安装或重新导入后看 diff。

第三层是 Codex plugins。
插件不是 skill，不纳入 `.agents/skills`。
插件用 `codex plugin list`、marketplace 和版本号单独记录。

## Profile 语义

`profiles/core` 只放稳定自研或长期自维护的最小集。

`profiles/global-runtime` 是本机 `~/.agents/skills` 的真相源。

`profiles/mattpocock-skills` 只放来自 `mattpocock/skills` 的外部 skill。

`profiles/codemao` 放公司 GitLab 内源 skill。

`profiles/vendor-lab` 放 EveryInc、其它 GitHub 大佬和开源 vendor 候选。

`profiles/experimental` 放临时试验和待归类 skill。

`profiles/web`、`profiles/ppt`、`profiles/basketball` 放明确专业场景的正式 skill。

`profiles/web-lab` 和 `profiles/ppt-lab` 放对应专业场景的实验候选。

`profiles/rtk-candidates` 放 RTK 本地候选，未确认长期保留前不进 core。

不要再使用 `profiles/all`。

## 新来源进入规则

GitHub 个人或 vendor 仓库先进入 `profiles/vendor-lab`，除非它明显属于 `ppt-lab` 或 `web-lab`。

公司 GitLab 仓库先进入 `profiles/codemao`。

`mattpocock/skills` 继续只进入 `profiles/mattpocock-skills`。

本地自研 skill 先进入最贴近的专业 profile 或 `profiles/experimental`。

只有确认长期复用、触发边界稳定、没有明显重复时，才晋级到 `profiles/core` 或 `profiles/global-runtime`。

## 晋级到全局的标准

一个 skill 进入 `profiles/global-runtime` 前，需要满足三个条件。

第一，它是日常高频或跨项目稳定有用的能力。

第二，它的触发描述足够清楚，不会误触发并污染普通任务。

第三，它有明确来源和升级路径。

公司 skill 进入全局前，还需要确认不会依赖过多本地临时数据、个人登录态或一次性输出。

## 升级规则

外部 GitHub skill 使用 Vercel `skills` CLI 在对应 profile 里重新安装。

安装命令优先使用 `--copy`，因为业务项目复用的是整个 `.agents` 目录。

公司 GitLab skill 优先从 upstream 根目录源 skill 复制到 `profiles/codemao/.agents/skills`。

复制时排除运行数据、历史审查结果、截图输出、临时产物和凭证。

升级后必须看 Git diff。

进入 `profiles/global-runtime` 的外部来源 skill，还必须在 `profiles/global-runtime/UPSTREAM.md` 记录 canonical source 和同步策略。
跨 skill 的个人触发、重试和时间预算应放在全局 `AGENTS.md`，不要作为本地补丁写回可跟随上游的运行副本。

不要直接在 `~/.agents/skills` 里改文件。

需要全局可用时，先改 `profiles/global-runtime/.agents/skills`，再让 `~/.agents/skills` 通过软链跟随。

## Lock 规则

Lock 是 profile 级文件，文件名是 `skills-lock.json`。

不要给每个 skill 单独创建 `skill.lock`。

外部或公司来源 profile 必须保留 `skills-lock.json`，至少包括 `profiles/mattpocock-skills`、`profiles/codemao`、`profiles/vendor-lab` 和 `profiles/experimental`。

`profiles/vendor-lab` 即使暂时为空，也保留空 lock，表示这是一个等待接入 vendor skill 的受管 profile。

自研 profile 可以没有 lock，因为当前 Git 仓库本身就是源。

业务项目从 `imchao9/skills/profiles/<profile>` 安装后，也应该提交目标项目自己的 `skills-lock.json`。

## 项目使用规则

项目采用“本机共研软链、长期交付复制”的双模式。

### 模式一：本机共研软链

只有同时满足以下条件时才使用软链：

- 项目和本仓库位于同一台机器，并且 canonical profile 路径稳定。
- 项目明确需要实时跟随 profile 工作区的未提交变化。
- `.agents/skills` 中没有需要独立版本化的项目私有 skill。
- 项目不依赖该绝对路径运行 CI、远程部署或跨机器协作。
- 修改软链内文件等同于修改 canonical profile，使用者理解这个副作用。

优先只链接 `.agents/skills`，保留项目自己的其它 `.agents` 配置：

```bash
mkdir -p .agents
ln -s /Users/cm/Documents/Me/skills/profiles/<profile>/.agents/skills \
  .agents/skills
```

替换已有目录前必须检查差异和 Git 状态，并把原目录改名备份；不要直接删除未确认内容。
绝对软链属于本机运行配置，不提交到需要在其它机器、CI 或服务器运行的仓库。

以下位置适合保持软链：

- `~/.agents/skills` 到 `profiles/global-runtime/.agents/skills`。
- 本仓库根目录 `.agents` 到默认 `profiles/core/.agents`。
- 像 `Basketball_videos` 这样与某个专业 profile 同机共研、需要实时回灌的本地项目。

### 模式二：Git Source 复制安装

长期业务项目、多人协作项目、需要 CI/远程部署的项目，以及需要锁定已审核版本的项目，默认从 GitHub source 安装某个 profile。
Git source 安装使用 `--copy`，因此目标项目拿到的是复制后的 `.agents/skills`，不是对本仓库的引用。
项目升级时需要重新运行同一条 Git source `add` 命令，并提交目标项目自己的 `.agents/skills` 和 `skills-lock.json`。

例如：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/core \
  --agent codex --skill '*' --yes --copy --full-depth
```

如果只需要单个 skill，在同一个 Git source 后面指定 `--skill <skill-name>`。

例如：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill technical-html-deck --yes --copy --full-depth
```

Git source 只包含已经提交并推送到 GitHub 的内容。
本地未提交或未推送的 profile 变化，不能作为其它项目的升级来源。

本地路径复制安装只用于验证当前未推送改动。
不要在 profile 之间用软链替代晋级和审查：`global-runtime` 仍按
`UPSTREAM.md` 对来源 profile 逐项同步；`codemao`、vendor、experimental
等 profile 仍保留复制快照和 lock。

不要把所有 profile 混装到业务项目，除非明确要做一次全量调试。

## 清理规则

发现重复 skill 时，先判断哪个 profile 是真相源。

通用稳定项优先留在 `profiles/global-runtime`，Codex 专属本地工具优先留在 `~/.codex/skills`。

删除前先确认是否有 Git 跟踪或备份路径。

未备份的物理文件删除属于破坏性操作，需要先确认。

## 插件规则

Codex plugins 只在 `docs/codex-plugins-inventory.md` 记账。

插件能力不要复制到 `.agents/skills`。

插件升级、启用和禁用走 Codex plugin 体系，不走 profile 晋级体系。
