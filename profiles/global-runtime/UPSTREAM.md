# Global Runtime Sources

本文记录 `profiles/global-runtime` 中外部来源 skill 的同步关系和本地覆盖策略。
更新运行态前必须先查看本文件，禁止用整个 profile 的盲目覆盖代替逐项合并。

## Source families

| Runtime scope | Canonical source | Policy |
| --- | --- | --- |
| `agent-reach` | `profiles/web/.agents/skills/agent-reach` | `follow`：先更新正式 profile，再完整同步到运行态；个人触发、重试和时间预算放在 `/Users/cm/.codex/AGENTS.md`，不修改运行副本。 |
| `technical-html-deck` | `profiles/ppt/.agents/skills/technical-html-deck` | `follow`：正式 profile 验证通过后完整同步。 |
| `drawio-skill` | `profiles/ppt/.agents/skills/drawio-skill`，上游 `Agents365-ai/drawio-skill` | `follow-after-review`：只作为 `technical-html-deck` 的可编辑技术图 renderer；保持显式触发和本地窄 wrapper。 |
| `fireworks-tech-graph` | `profiles/ppt/.agents/skills/fireworks-tech-graph`，上游 `yizhiyanhua-ai/fireworks-tech-graph` | `follow-after-review`：只作为 `technical-html-deck` 的语义 SVG renderer；保持显式触发和本地窄 wrapper。 |
| 与 `profiles/mattpocock-skills` 同名且未列入例外的 skill | `profiles/mattpocock-skills/.agents/skills/<name>` | `follow-after-review`：来源 profile 更新后逐项看 diff，再同步到运行态；禁止整个目录盲目覆盖。 |
| `ce-compound` | `profiles/experimental/.agents/skills/ce-compound` | `follow-after-review`：实验版本验证通过后再晋级同步。 |
| `obsidian-vault` | Local maintained fork of `profiles/mattpocock-skills/.agents/skills/obsidian-vault` | `local-fork`：不允许上游覆盖；上游只用于人工 diff；本地版本负责真实 vault 路径、结构保护和 Codex-Memory 规则。 |
| `accept-tech-plan`、`cg-gen`、`cg-req`、`codemao-learning`、`codemao-troubleshoot`、`crp-deploy`、`dingtalk-mcp-reader`、`feign-client-example-generator`、`java-backend-code-review`、`java-backend-knowledge-base`、`market-live-report-skill` | `git@gitlab.codemao.cn:backend/platform-informatization/tool/skills.git`，经 `profiles/codemao` 维护 | `follow-after-review`：先刷新公司 profile、清理 `data/`、`output/` 和缓存等运行产物，再逐项同步到运行态。`codemao-learning` 已同步到来源 profile 记录的 upstream commit `882508ed31f992fd5212d13d281f287368ccb1cf`；其余全局副本仍基于 `64a5c38db558820cccd2de87b002ad1fadb82904` 或保持各自已审查版本。 |

## Unresolved provenance

以下运行态 skill 当前没有可确认的同名 canonical profile，升级前必须先补齐来源：

- `agently-mail`
- `notebooklm`

`to-issues` 和 `to-prd` 已随 `mattpocock-skills` 的来源删除从运行态移除。
如上游以后重新提供同名 skill，按 `follow-after-review` 重新评估，不自动恢复。

`design-an-interface`、`qa`、`request-refactor-plan` 和 `ubiquitous-language` 仍保留在 `profiles/mattpocock-skills` 的上游镜像中，但不进入 `global-runtime`。
它们位于 matt 上游的 deprecated 分组；如需恢复到运行态，必须重新说明使用场景并人工评估。

`profiles/mattpocock-skills` 当前基于 upstream commit `ed37663`。
除 `obsidian-vault` 本地 fork 外，运行态中与 matt source 同名的 skill 已同步到该来源。

如果一个运行态 skill 不属于上述来源族，先通过 Git 历史和真实来源补充记录，再执行升级。

## Upgrade workflow

1. 在来源 profile 更新或重新安装上游 skill。
2. 查看来源 profile 的 Git diff，确认上游变化。
3. 对 `follow` 项完整同步，对 `local maintained fork` 项执行人工 diff 和选择性合并。
4. 检查全局 `AGENTS.md` 的跨 skill 护栏仍然有效。
5. 验证 skill frontmatter、真实触发边界和最小 smoke case 后，再提交仓库。
