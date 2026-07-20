# Personal Skills

这个仓库只做一件事：按 profile 保存可直接复用的 `.agents` 目录。Git 就是版本管理，Vercel `skills` CLI 只是安装器。

其他项目不需要初始化命令、不需要角色/pack/preset，也不需要 CStack 那套装配关系。
默认从这个 GitHub 仓库安装某个 profile，让目标项目生成自己的 `.agents/skills` 和 `skills-lock.json`。
本地路径和软链只用于本机开发、调试或临时验证。

## 目录

```text
profiles/
  global-runtime/
    .agents/
      skills/
        <skill-name>/
          SKILL.md
  core/
    .agents/
      skills/
        <skill-name>/
          SKILL.md

.agents -> profiles/core/.agents
```

`profiles/core` 是当前默认 profile，只放稳定、确定自研或长期自维护的核心 skill。根目录 `.agents` 只是一个方便入口，指向 `profiles/core/.agents`。
`profiles/global-runtime` 是本机全局运行态的真相源。
`~/.agents/skills` 软链到 `profiles/global-runtime/.agents/skills`，不要手动维护全局目录里的文件。

## Profile 分层

```text
profiles/core/                # 默认最小集，稳定自研核心
profiles/global-runtime/      # 本机 ~/.agents/skills 的真相源
profiles/ppt/                 # 正式 PPT / HTML 演示稿生产链路
profiles/ppt-lab/             # PPT skill 实验候选
profiles/web/                 # 正式联网入口，目前只保留 agent-reach
profiles/web-lab/             # Firecrawl / XCrawl / browser-use 等实验候选
profiles/mattpocock-skills/   # 来自 mattpocock/skills 的外部 skill
profiles/codemao/             # 公司 GitLab 内源 skill
profiles/vendor-lab/          # EveryInc / GitHub 大佬 / 开源 vendor 候选
profiles/rtk-candidates/      # RTK 本地候选，未确认是否长期保留
profiles/experimental/        # 其它实验或待归类 skill
profiles/basketball/          # 篮球视频专用
```

## 全局运行态

本机全局 skills 以这个仓库里的 `profiles/global-runtime` 为准。

```text
~/.agents/skills -> /Users/cm/Documents/Me/skills/profiles/global-runtime/.agents/skills
```

`~/.agents/plugins`、`~/.agents/.skill-lock.json` 仍保留在全局目录里，避免影响 Codex plugin marketplace 和 `skills` CLI 的安装记录。
不要直接编辑 `~/.agents/skills`。
需要新增或升级全局 skill 时，先更新 `profiles/global-runtime/.agents/skills`，再提交这个仓库。

Codex plugins 不进入 `.agents/skills`。
插件 inventory 记录在 `docs/codex-plugins-inventory.md`。
skills 的来源分层、晋级和清理规则记录在 `docs/skills-governance.md`。

## Skill 调试台

新发现的 skill 不直接进入 profile，先进入调试台：

```text
debug/
  cases/      # 可复用调用用例
  intake/     # 新 skill 初筛记录
  runs/       # 每次真实调用产物和效果记录
  index.html  # 效果对比页面
```

打开调试台：

```bash
cd /Users/cm/Documents/me/skills/debug
python3 -m http.server 8765
```

然后访问：

```text
http://127.0.0.1:8765/
```

入库原则：每个进入正式 profile 的 skill，至少要有一条可复现 case 和一条 run 记录；视觉/PPT 类 skill 还要保存预览图，方便直接对比效果。

## 用在其他项目

### 方式一：Git Source 安装

这是推荐方式。
目标项目应根据 Git 仓库安装和升级，而不是依赖本机目录手工复制。
这种方式会把 skill 复制进目标项目自己的 `.agents/skills/`，不是引用本仓库目录。

在目标项目根目录执行，安装默认 core profile：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/core \
  --agent codex --skill '*' --yes --copy --full-depth
```

安装 PPT profile：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

只安装 `technical-html-deck`：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill technical-html-deck --yes --copy --full-depth
```

Git source 只会看到已经提交并推送到 GitHub 的内容。
本地未提交或未推送的 profile 变化，不会被其它项目安装到。

Lock 是 profile 级 `skills-lock.json`，不是每个 skill 一个 `skill.lock`。
外部或公司来源 profile 需要保留 lock；自研 profile 可以没有 lock。

### 方式二：软链复用

软链只用于本机开发、调试或明确要跟随本仓库工作区实时变化的项目。

在目标项目根目录执行，使用默认 profile：

```bash
ln -s /Users/cm/Documents/Me/skills/.agents .agents
```

或者明确选择某个 profile：

```bash
ln -s /Users/cm/Documents/Me/skills/profiles/core/.agents .agents
```

如果目标项目已经有 `.agents`，先手动确认里面有没有项目私有内容，再决定是否替换。

### 方式三：本地路径安装

本地路径安装只用于验证当前未推送改动。
不要把它作为其它长期项目的默认安装方式。

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/core \
  --agent codex --skill '*' --yes --copy --full-depth
```

查看某个 profile 会安装哪些 skill：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --list --full-depth
```

实测 Git source 支持 profile 子路径，例如 `imchao9/skills/profiles/ppt`。
目标项目应优先记录 Git source 的 `skills-lock.json`，后续升级重新运行同一条 Git source `add` 命令，或在 CLI 支持时使用 `skills update`。
当前 `skills@latest` 对 local source 的 `npx skills update --project` 不生效；本地路径安装只作为未推送改动的临时验证。

## 升级全局和项目

升级全局运行态：

1. 先更新对应来源 profile，例如 `profiles/mattpocock-skills`、`profiles/web`、`profiles/codemao`。
2. 按 `profiles/global-runtime/UPSTREAM.md` 逐项同步到 `profiles/global-runtime/.agents/skills`。
3. 验证 `profiles/global-runtime/.agents` 能被 `skills@latest` 识别。
4. 提交并推送本仓库。

因为 `~/.agents/skills` 是软链到 `profiles/global-runtime/.agents/skills`，全局运行态会实时跟随本仓库工作区。

升级业务项目：

1. 先确保本仓库的 profile 变更已经 commit 并 push。
2. 在目标项目根目录重新运行原来的 Git source `add` 命令。
3. 提交目标项目更新后的 `.agents/skills/` 和 `skills-lock.json`。

例如同步 PPT profile：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

判断项目当前是不是引用：

- 如果目标项目 `.agents` 是 symlink，它是引用，会跟随源 profile 实时变化。
- 如果目标项目 `.agents/skills/<skill-name>/SKILL.md` 是普通文件，它是复制安装，需要重新运行 `npx skills add` 才会升级。
- 长期项目默认使用复制安装，只有本机调试项目才建议使用 symlink。

## 添加新的 Skill

只在这个仓库的某个 profile 里维护 skills，其他项目通过 Git source 安装和升级。

```bash
cd /Users/cm/Documents/Me/skills/profiles/mattpocock-skills
env -u http_proxy -u https_proxy -u all_proxy npx --yes skills@latest add mattpocock/skills --agent codex --skill '*' --yes --copy
```

已验证 `mattpocock/skills` 会安装：

```text
.agents/skills/grill-with-docs/
```

安装其他来源也用同一形态：

```bash
env -u http_proxy -u https_proxy -u all_proxy npx --yes skills@latest add <owner>/<repo> --agent codex --skill '*' --yes --copy
```

然后提交 `profiles/<profile>/.agents/skills/` 的变化即可。
这里使用 `--copy`，因为本仓库直接跟踪安装后的 skill 文件。
其它业务项目不读取本机路径，而是从 `imchao9/skills/profiles/<profile>` 安装。

## 管理自研 Skill

自己生成或长期维护的 skill 也统一放在这个仓库里管理。正式维护入口是：

```text
profiles/<profile>/.agents/skills/<skill-name>/
```

推荐规则：

- 先放到最相关的专业 profile，例如 PPT 相关放 `profiles/ppt/.agents/skills/`，网页抓取相关放 `profiles/web/.agents/skills/`。
- 确认会被多个场景长期复用后，再晋级到 `profiles/core/.agents/skills/`、`profiles/global-runtime/.agents/skills/` 或对应正式 profile。
- 半成品、对比实验、效果截图、调试用例放 `debug/`，不要直接进入正式 profile。
- 每个正式 skill 至少保留 `SKILL.md`；需要 UI 展示时加 `agents/openai.yaml`；复杂流程再加 `references/`、`scripts/`、`assets/`。
- `SKILL.md` 只写会改变 agent 行为的流程和规则；详细风格、案例、评分表放到 `references/`。

推荐创建方式：

```bash
rtk proxy python3 /Users/cm/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  <skill-name> \
  --path /Users/cm/Documents/me/skills/profiles/<profile>/.agents/skills \
  --resources references,scripts
```

创建后用真实 case 跑一遍，把输入、输出和截图放到 `debug/runs/<date>-<slug>/`。确认稳定后再同步到 `profiles/core`、对应正式 profile 或目标项目。

## 更新 Skill 版本

更新就是在对应 profile 里重新跑同一条 Vercel 安装命令，让它覆盖旧文件，然后看 Git diff：

```bash
cd /Users/cm/Documents/Me/skills/profiles/mattpocock-skills
env -u http_proxy -u https_proxy -u all_proxy npx --yes skills@latest add mattpocock/skills --agent codex --skill '*' --yes --copy
git diff
```

确认无误后提交变化。这个仓库不额外维护 lock/restore 流程。

## 查看当前 Profile

查看当前 skills：

```bash
cd /Users/cm/Documents/Me/skills/profiles/core
env -u http_proxy -u https_proxy -u all_proxy npx --yes skills@latest list --json
```

## 检查全局碰撞

这个仓库不安装到全局 `~/.agents`。全局目录只用来对照是否有同名 skill：

```bash
cd /Users/cm/Documents/Me/skills
comm -12 \
  <(find profiles/core/.agents/skills -mindepth 1 -maxdepth 1 -type d -exec sh -c '[ -f "$1/SKILL.md" ] && basename "$1"' sh {} \; | sort) \
  <(find /Users/cm/.agents/skills -mindepth 1 -maxdepth 1 -type d -exec sh -c '[ -f "$1/SKILL.md" ] && basename "$1"' sh {} \; 2>/dev/null | sort)
```

无输出表示没有同名碰撞。
