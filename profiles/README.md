# Profiles

每个 profile 都可以作为一个本地 `npx skills` source 使用。推荐在新项目里按 profile 安装，而不是安装整个 `profiles/` 根目录。

## 安装某个 Profile

在目标项目根目录执行：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/<profile> \
  --agent codex --skill '*' --yes --copy --full-depth
```

示例：安装 PPT profile。

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

## 当前 Profile

| Profile | 用途 |
|---|---|
| `core` | 默认最小集，稳定自研或长期自维护 skill |
| `ppt` | 正式 PPT / HTML 演示稿生产链路 |
| `ppt-lab` | PPT skill 实验候选 |
| `web` | 正式联网入口，目前只保留 `agent-reach` |
| `web-lab` | Firecrawl / XCrawl / browser-use 等实验候选 |
| `mattpocock-skills` | 来自 `mattpocock/skills` 的外部 skill |
| `rtk-candidates` | RTK 本地候选 skill |
| `experimental` | 其它实验或待归类 skill |
| `basketball` | 篮球视频专用，包括纯享版剪辑和集锦生成 |

不要再使用 `profiles/all`。

安装后会在目标项目生成：

```text
.agents/skills/<skill-name>/SKILL.md
skills-lock.json
```

## 查看某个 Profile 包含什么

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/<profile> \
  --list --full-depth
```

## 安装单个 Skill

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/ppt \
  --agent codex --skill ppt-master --yes --copy --full-depth
```

## 同步更新到目标项目

当前 `skills@latest` 可以从本地 profile 安装并生成 `skills-lock.json`，但实测 `npx skills update --project` 不会处理这种 local source。要把 profile 里的新版本同步到目标项目，重新运行同一条 `add` 命令即可覆盖安装。

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

## 不推荐直接安装 profiles 根目录

下面这条命令可以工作，但会把所有 profile 下的 skill 混合安装到同一个目标项目：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles \
  --agent codex --skill '*' --yes --copy --full-depth
```

只有在明确想安装全部 skill 时才使用它。
