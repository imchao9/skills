# Global Runtime Sources

本文记录 `profiles/global-runtime` 中外部来源 skill 的同步关系和本地覆盖策略。
更新运行态前必须先查看本文件，禁止用整个 profile 的盲目覆盖代替逐项合并。

## Source families

| Runtime scope | Canonical source | Policy |
| --- | --- | --- |
| `ai-intelligent-test` | `profiles/codemao/.agents/skills/ai-intelligent-test`，内部执行框架 `git@gitlab.codemao.cn:frontend/student/ai-intelligent-test.git` | `local-fork`：只维护跨项目入口、仓库定位和 backend 路由；内部 6 个 repo skills 留在 `profiles/codemao` 跟随来源，不整体复制到运行态。 |
| `agent-reach` | `profiles/web/.agents/skills/agent-reach` | `follow`：先更新正式 profile，再完整同步到运行态；个人触发、重试和时间预算放在 `/Users/cm/.codex/AGENTS.md`，不修改运行副本。 |
| `technical-html-deck` | `profiles/ppt/.agents/skills/technical-html-deck` | `follow`：正式 profile 验证通过后完整同步。 |
| `drawio-skill` | `profiles/ppt/.agents/skills/drawio-skill`，上游 `Agents365-ai/drawio-skill` | `follow-after-review`：只作为 `technical-html-deck` 的可编辑技术图 renderer；保持显式触发和本地窄 wrapper。 |
| `fireworks-tech-graph` | `profiles/ppt/.agents/skills/fireworks-tech-graph`，上游 `yizhiyanhua-ai/fireworks-tech-graph` | `follow-after-review`：只作为 `technical-html-deck` 的语义 SVG renderer；保持显式触发和本地窄 wrapper。 |
| 与 `profiles/mattpocock-skills` 同名且未列入例外的 skill | `profiles/mattpocock-skills/.agents/skills/<name>` | `follow-after-review`：来源 profile 更新后逐项看 diff，再同步到运行态；禁止整个目录盲目覆盖。 |
| `grok-research` | `profiles/experimental/.agents/skills/grok-research` | `follow-after-review`：本地自研的 OpenCLI Browser Bridge 研究流程；保持 Grok 显式触发、X/YouTube 窄范围、原始链接核验和浏览器状态护栏，来源版本验证后完整同步。 |
| `obsidian-vault` | Local maintained fork of `profiles/mattpocock-skills/.agents/skills/obsidian-vault` | `local-fork`：不允许上游覆盖；上游只用于人工 diff；本地版本负责真实 vault 路径、结构保护和 Codex-Memory 规则。 |
| `codemao-troubleshoot` | `profiles/codemao/.agents/skills/codemao-troubleshoot` | `local-fork`：业务逻辑继续人工跟随公司来源；运行态 `package-lock.json` 将间接依赖 `ip-address` 锁定到 `10.4.0`，修复已知 SSRF/地址分类绕过风险，上游刷新不得降级该安全修复。 |
| `accept-tech-plan`、`cg-gen`、`cg-req`、`codemao-learning`、`dingtalk-mcp-reader`、`feign-client-example-generator`、`java-backend-code-review`、`java-backend-knowledge-base`、`market-live-report-skill` | `git@gitlab.codemao.cn:backend/platform-informatization/tool/skills.git`，经 `profiles/codemao` 维护 | `follow-after-review`：先刷新公司 profile、清理 `data/`、`output/` 和缓存等运行产物，再逐项同步到运行态。`codemao-learning` 已同步到来源 profile 记录的 upstream commit `882508ed31f992fd5212d13d281f287368ccb1cf`；其余全局副本仍基于 `64a5c38db558820cccd2de87b002ad1fadb82904` 或保持各自已审查版本。 |

2026-07-28 来源快照：`agent-reach` 已跟随上游 `b4d52c46c9113cb0f653d6df4cf71ebadf4930ac`；`ce-compound` 已审查并同步上游 `a9f6d530d4446d805a3100387dedd86268d7e695`；`drawio-skill` 已选择性吸收上游 `719fd3663b7ec702e2ff969231f42e167c3d556b` 的 edge port 能力并保留本地窄 wrapper。`profiles/codemao` 已刷新到 `d98cf06ce4cd742dd2a877c8f9159ce8cbce33b1`，但本次未把其新增或扩权变化同步到全局。

## Runtime exclusions

- `ce-compound` 继续保留在 `profiles/experimental` 供来源审查，但不进入全局运行态；其完成后沉淀行为必须由用户显式选择。
- `crp-deploy` 继续保留在 `profiles/codemao` 供公司场景按需安装，但不进入全局运行态；部署、认证和外部写入需要独立人工门禁。
- `research` 和 `code-review` 保留在运行态，但通过 `disable-model-invocation: true` 限制为显式调用，避免普通调研和小型审查自动进入重型工作流。

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
