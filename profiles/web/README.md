# Web Profile

这个 profile 是正式联网入口，目前只保留：

| Skill | 来源 | 说明 |
|---|---|---|
| `agent-reach` | `Panniantong/agent-reach` | 多平台搜索、网页阅读、GitHub、社交平台调研的路由器 |

选择 `agent-reach` 的原因：它已经是联网能力路由层，覆盖搜索、网页、GitHub、社交平台和多后端选择；比同时安装 Firecrawl / XCrawl / browser-use 更适合作为默认入口，能减少触发冲突和工具选择成本。

其它联网 / 抓取 / 浏览器自动化候选已移到：

```text
/Users/cm/Documents/me/skills/profiles/web-lab
```

## Usage

在目标项目根目录从 GitHub source 安装整个 profile：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/web \
  --agent codex --skill '*' --yes --copy --full-depth
```

只安装 `agent-reach`：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/web \
  --agent codex --skill agent-reach --yes --copy --full-depth
```
