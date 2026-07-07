# Codemao Profile

公司 GitLab 内源 skill 的隔离 profile。

这些 skill 先在这里管理和评估，不直接灌进全局运行态。

## 来源

```text
git@gitlab.codemao.cn:backend/platform-informatization/tool/skills.git
```

当前导入的 upstream commit：

```text
2adf6591ac3b6210e364b40943e6ac8978248775
```

导入时使用根目录 skill 源文件，不使用 upstream 的 `.agents/skills/` 生成态。

运行产物没有导入，例如 `data/review-findings.jsonl` 和 `output/`。

## 当前包含

- `accept-tech-plan`
- `cg-gen`
- `codemao-troubleshoot`
- `crp-deploy`
- `dingtalk-mcp-reader`
- `feign-client-example-generator`
- `java-backend-code-review`
- `java-backend-knowledge-base`
- `market-live-report-skill`

## 升级方式

先刷新 upstream 仓库，再复制根目录 skill 源文件到本 profile。

复制后必须看 Git diff，确认没有带入运行数据、凭证、历史审查结果或机器本地输出。

稳定高频的公司 skill 可以从这里晋级到 `profiles/global-runtime`，但晋级时需要说明触发场景和保留理由。
