# Web / Crawl Skill 评估与安装报告

评估日期：2026-07-02

来源：

- X: https://x.com/369Serena/status/2068550047713661407

识别到的 5 个项目：

- Agent-Reach: https://github.com/Panniantong/agent-reach
- Firecrawl: https://github.com/firecrawl/firecrawl
- Crawl4AI: https://github.com/unclecode/crawl4ai
- browser-use: https://github.com/browser-use/browser-use
- XCrawl: https://github.com/xcrawl-api/xcrawl

## 结论

已创建并安装到：

```text
/Users/cm/Documents/me/skills/profiles/web
```

最终包含 20 个可安装 skills：

```text
agent-reach
browser-use
crawl4ai
firecrawl
firecrawl-agent
firecrawl-crawl
firecrawl-download
firecrawl-interact
firecrawl-map
firecrawl-monitor
firecrawl-parse
firecrawl-scrape
firecrawl-search
open-source
remote-browser
xcrawl
xcrawl-crawl
xcrawl-map
xcrawl-scrape
xcrawl-search
```

安装命令：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/web \
  --agent codex --skill '*' --yes --copy --full-depth
```

## 逐项评估

| 项目 | npx skills 结果 | 安装处理 | 备注 |
|---|---|---|---|
| Agent-Reach | `Panniantong/agent-reach` 可发现 1 个 skill | 已安装 `agent-reach` | CLI 安全扫描提示 Socket 1 alert / Snyk High Risk；本地已修 frontmatter |
| Firecrawl | `firecrawl/firecrawl` 本体无 SKILL.md | 改用 `firecrawl/cli`，安装 10 个 skills | 对应官方 CLI skill 包；本体不直接安装 |
| Crawl4AI | `unclecode/crawl4ai` 本体无 SKILL.md | 改用 `brettdavies/crawl4ai-skill`，安装 `crawl4ai` | 对应可安装 skill 包；本地已修 frontmatter |
| browser-use | `browser-use/browser-use` 可发现 6 个 skills | 保留 3 个：`browser-use`, `open-source`, `remote-browser` | 移除 `cloud`, `qa`, `x402`，避免泛名和支付/钱包风险 |
| XCrawl | `xcrawl-api/xcrawl-skills` 可发现 5 个 skills | 全部安装 | `xcrawl-search` 被 CLI 标为 Snyk High Risk |

## 校验

`npx skills` 发现：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/web \
  --list --full-depth
```

结果：发现 20 个 skills。

临时新项目安装：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/web \
  --agent codex --skill '*' --yes --copy --full-depth
```

结果：安装 20 个 skills 到 `.agents/skills/`。

严格结构校验：

```bash
for d in /Users/cm/Documents/me/skills/profiles/web/.agents/skills/*; do
  /Users/cm/Documents/me/skill_check/.venv-skill-eval/bin/python \
    /Users/cm/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$d"
done
```

结果：20 个均通过。

## 风险和使用建议

- 这批 skill 都是联网/浏览器/抓取能力，默认具有较高权限风险；在敏感项目里按需只装单个 skill。
- `agent-reach`、`crawl4ai`、`xcrawl-search` 有 High Risk 提示，建议先跑 debug case 再作为默认能力使用。
- Firecrawl 和 XCrawl 多数能力依赖外部 CLI/API key；没有配置时可能只能进入说明/命令规划阶段。
- Browser Use 包里的 `x402` 涉及支付/钱包，未安装进默认 profile。
- 不建议把 `profiles/web` 和 `profiles/all` 混装到同一项目；存在泛名 skill 潜在冲突，例如 `open-source`。

## 后续调试

已新增 baseline cases：

```text
/Users/cm/Documents/me/skills/debug/cases/web
```

调试台：

```text
http://127.0.0.1:8765/
```
