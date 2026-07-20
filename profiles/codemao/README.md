# Codemao Profile

公司 GitLab 内源 skill 的隔离 profile。

这些 skill 先在这里管理和评估，不直接灌进全局运行态。

## 来源

```text
git@gitlab.codemao.cn:backend/platform-informatization/tool/skills.git
```

当前导入的 upstream commit：

```text
882508ed31f992fd5212d13d281f287368ccb1cf
```

导入时使用根目录 skill 源文件，不使用 upstream 的 `.agents/skills/` 生成态。

运行产物没有导入，例如 `data/review-findings.jsonl` 和 `output/`。

## 当前包含

- `accept-tech-plan`
- `cg-gen`
- `cg-req`
- `codemao-learning`
- `codemao-troubleshoot`
- `crp-deploy`
- `dingtalk-mcp-reader`
- `feign-client-example-generator`
- `java-backend-code-review`
- `java-backend-knowledge-base`
- `lingxi-code`
- `lingxi-plan`
- `market-live-report-skill`

本次刷新时，CLI 从 upstream 根目录发现 11 个 skill；`cg-gen` 和 `cg-req` 未出现在发现结果中，但现有副本与 lock 条目暂时保留，等待确认是否属于上游删除后再清理。

## 升级方式

在本目录重新执行同一条 GitLab source 安装命令即可。
命令会自动发现 upstream 新增的 skill，并更新 `skills-lock.json`。

```bash
cd /Users/cm/Documents/Me/skills/profiles/codemao
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add \
  git@gitlab.codemao.cn:backend/platform-informatization/tool/skills.git \
  --agent codex --skill '*' --yes --copy --full-depth
```

更新后必须看 Git diff，确认没有带入运行数据、凭证、历史审查结果或机器本地输出。
`data/`、`output/` 和 Python 缓存目录不纳入本 profile 的 Git 内容。

稳定高频的公司 skill 可以从这里晋级到 `profiles/global-runtime`，但晋级时需要说明触发场景和保留理由。
