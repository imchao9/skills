# Personal Skills

这个仓库只做一件事：按 profile 保存可直接复用的 `.agents` 目录。Git 就是版本管理，Vercel `skills` CLI 只是安装器。

其他项目不需要初始化命令、不需要角色/pack/preset，也不需要 CStack 那套装配关系。默认可以选一个 profile，把它的 `.agents` 整体软链过去；如果希望在目标项目里复制一份安装态，也可以直接用 `npx skills add profiles/<profile>`。

## 目录

```text
profiles/
  all/
    .agents/
      skills/
        <skill-name>/
          SKILL.md

.agents -> profiles/all/.agents
```

`profiles/all` 是当前默认 profile。根目录 `.agents` 只是一个方便入口，指向 `profiles/all/.agents`。

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

### 方式一：软链复用

在目标项目根目录执行，使用默认 profile：

```bash
ln -s /Users/cm/Documents/Me/skills/.agents .agents
```

或者明确选择某个 profile：

```bash
ln -s /Users/cm/Documents/Me/skills/profiles/all/.agents .agents
```

后续如果有 `profiles/backend/.agents`、`profiles/writing/.agents`、`profiles/design/.agents`，目标项目只需要把 symlink 换到对应 profile。

如果目标项目已经有 `.agents`，先手动确认里面有没有项目私有内容，再决定是否替换。

### 方式二：npx skills 复制安装

在目标项目根目录执行，按 profile 安装：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/all \
  --agent codex --skill '*' --yes --copy --full-depth
```

安装 PPT profile：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

查看某个 profile 会安装哪些 skill：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/ppt \
  --list --full-depth
```

实测 `npx skills add /Users/cm/Documents/me/skills/profiles/<profile> --agent codex --skill '*' --yes --copy --full-depth` 会在目标项目生成 `.agents/skills/` 和 `skills-lock.json`。当前 `skills@latest` 对 local source 的 `npx skills update --project` 不生效；需要同步 profile 更新时，重新运行同一条 `add` 命令覆盖安装。

## 添加新的 Skill

只在这个仓库的某个 profile 里安装 skills，其他项目通过软链共享结果。

```bash
cd /Users/cm/Documents/Me/skills/profiles/all
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

然后提交 `profiles/<profile>/.agents/skills/` 的变化即可。这里使用 `--copy`，因为软链的是整个 `.agents` 目录；每个业务项目不再单独安装一份。

## 管理自研 Skill

自己生成或长期维护的 skill 也统一放在这个仓库里管理。正式维护入口是：

```text
profiles/<profile>/.agents/skills/<skill-name>/
```

推荐规则：

- 先放到最相关的专业 profile，例如 PPT 相关放 `profiles/ppt/.agents/skills/`，网页抓取相关放 `profiles/web/.agents/skills/`。
- 确认会被多个场景长期复用后，再复制到 `profiles/all/.agents/skills/`。
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

创建后用真实 case 跑一遍，把输入、输出和截图放到 `debug/runs/<date>-<slug>/`。确认稳定后再同步到 `profiles/all` 或目标项目。

## 更新 Skill 版本

更新就是在对应 profile 里重新跑同一条 Vercel 安装命令，让它覆盖旧文件，然后看 Git diff：

```bash
cd /Users/cm/Documents/Me/skills/profiles/all
env -u http_proxy -u https_proxy -u all_proxy npx --yes skills@latest add mattpocock/skills --agent codex --skill '*' --yes --copy
git diff
```

确认无误后提交变化。这个仓库不额外维护 lock/restore 流程。

## 查看当前 Profile

查看当前 skills：

```bash
cd /Users/cm/Documents/Me/skills/profiles/all
env -u http_proxy -u https_proxy -u all_proxy npx --yes skills@latest list --json
```

## 检查全局碰撞

这个仓库不安装到全局 `~/.agents`。全局目录只用来对照是否有同名 skill：

```bash
cd /Users/cm/Documents/Me/skills
comm -12 \
  <(find profiles/all/.agents/skills -mindepth 1 -maxdepth 1 -type d -exec sh -c '[ -f "$1/SKILL.md" ] && basename "$1"' sh {} \; | sort) \
  <(find /Users/cm/.agents/skills -mindepth 1 -maxdepth 1 -type d -exec sh -c '[ -f "$1/SKILL.md" ] && basename "$1"' sh {} \; 2>/dev/null | sort)
```

无输出表示没有同名碰撞。
