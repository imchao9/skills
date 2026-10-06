# Profiles

自创 Skill 的 canonical source 是仓库根目录 `skills/<skill-name>/`。本目录下的 profile 保存来源副本、组合说明和运行态快照；外部或公司来源的 profile 还必须保留来源证据。

每个 profile 都可以作为一个 Git source 子路径使用。
推荐在其它项目里从 GitHub 安装某个 profile，而不是从本机目录手工复制。

## 安装某个 Profile

在目标项目根目录执行：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/<profile> \
  --agent codex --skill '*' --yes --copy --full-depth
```

示例：安装 PPT profile。

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

自创 Skill 从仓库根目录按名称单独安装，不把整个仓库当成一个安装单元：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add \
  https://github.com/imchao9/skills/tree/main/skills/<skill-name> \
  --agent codex --copy --yes
```

Git source 只包含已经推送到 GitHub 的内容。
本地未提交或未推送的 profile 变化，需要先在本仓库提交并推送，或者临时使用本地路径安装做验证。

## 当前 Profile

| Profile | 用途 |
|---|---|
| `core` | 默认最小安装集合，成员可来自根目录 `skills/` 或来源 profile |
| `global-runtime` | 本机 `~/.agents/skills` 的真相源 |
| `ppt` | 正式 PPT / HTML 演示稿生产链路 |
| `ppt-lab` | PPT skill 实验候选 |
| `web` | 正式联网入口，目前只保留 `agent-reach` |
| `web-lab` | Firecrawl / XCrawl / browser-use 等实验候选 |
| `mattpocock-skills` | 来自 `mattpocock/skills` 的外部 skill |
| `software-factory` | 需求、架构、实现、验证、交付的组合 profile |
| `codemao` | 公司 GitLab 内源 skill |
| `vendor-lab` | EveryInc、GitHub 大佬和其它开源 vendor 候选 |
| `rtk-candidates` | RTK 本地候选 skill |
| `experimental` | 其它实验或待归类 skill |
| `basketball` | 篮球视频专用，包括纯享版剪辑和集锦生成 |

不要再使用 `profiles/all`。
不要直接维护 `~/.agents/skills`。
本机全局运行态应软链到 `profiles/global-runtime/.agents/skills`。

安装后会在目标项目生成：

```text
.agents/skills/<skill-name>/SKILL.md
skills-lock.json
```

## Lock 规则

Lock 是 profile 级 `skills-lock.json`，不是每个 skill 一个 `skill.lock`。

外部或公司来源 profile 需要保留 lock：

- `mattpocock-skills`
- `codemao`
- `vendor-lab`
- `experimental`

自创 Skill 的根目录 `skills/` 可以没有 profile 级 lock，因为这个仓库本身就是源。目标项目的复制安装和本机运行态都不是自创 Skill 的维护入口。

组合 profile 可以额外维护 manifest，声明每个 Skill 的来源 profile、来源路径和职责；例如
`profiles/software-factory/software-factory-set.json`。manifest 决定组合成员，`skills-lock.json`
记录安装来源和完整性。组合目录本地共研时可以由 manifest 生成特定 Skill 的相对软链，提交或通过
Git source 发布前应生成实体文件。

## 查看某个 Profile 包含什么

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/<profile> \
  --list --full-depth
```

## 安装单个 Skill

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill ppt-master --yes --copy --full-depth
```

## 同步更新到目标项目

目标项目同步 profile 更新时，重新运行同一条 Git source `add` 命令即可覆盖安装。
如果 CLI 后续对 Git source 的 `skills update` 支持稳定，可以改用 `skills update`。

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

## 本地路径安装

本地路径安装只用于验证当前未推送改动：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/Me/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

不要把本地路径安装作为其它长期项目的默认安装方式。
