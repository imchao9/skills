# Profiles

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

Git source 只包含已经推送到 GitHub 的内容。
本地未提交或未推送的 profile 变化，需要先在本仓库提交并推送，或者临时使用本地路径安装做验证。

## 当前 Profile

| Profile | 用途 |
|---|---|
| `core` | 默认最小集，稳定自研或长期自维护 skill |
| `global-runtime` | 本机 `~/.agents/skills` 的真相源 |
| `ppt` | 正式 PPT / HTML 演示稿生产链路 |
| `ppt-lab` | PPT skill 实验候选 |
| `web` | 正式联网入口，目前只保留 `agent-reach` |
| `web-lab` | Firecrawl / XCrawl / browser-use 等实验候选 |
| `mattpocock-skills` | 来自 `mattpocock/skills` 的外部 skill |
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

自研 profile 可以没有 lock，因为这个仓库本身就是源。

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
