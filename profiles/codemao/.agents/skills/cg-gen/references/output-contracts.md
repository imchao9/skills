# cg-gen Output Contracts

Use these contracts only when the main skill's Output Policy requires them.

## Compact Completion Output
Use this compact structure by default after successful `Implement Mode` code changes:

```markdown
## 主要改动点 (Main Changes)
- <file/module>: <intentional behavior change>
- 保护不变: <paths or behavior intentionally unchanged, when relevant>

## 交付清单符合情况 (Delivery Checklist Fit)
- 符合预期: <items, only when project checklist exists>
- 不符合预期: <items, only when project checklist exists>

## 风险/阻塞 (Risks/Blockers)
- <only if present>

## 交付决策 (Delivery Decision)
请选择：
1. 不落文档，不生成测试要点，结束任务
2. 只生成测试要点
3. 只把改动点落到文档
4. 改动点落到文档，并生成测试要点
```

If the user chooses test points, return:

```markdown
## 测试要点 (Test Points)
- 功能路径:
- 异常路径:
- 回归路径:
- 观测项:
```

## Detailed Audit Output
Use this detailed output when the user asks for audit/checklist detail, a hard gate fails, `Review-Only Mode` is selected, `Plan-Full` needs an explicit persistence decision, or compliance-sensitive evidence must be visible.

```markdown
## 预检查 (Pre-check)
### Core (Always)
- 触发画像 (Trigger Profile): `L0-Review | L1-Small | L2-Standard | L3-HighRisk`.
- 计划状态 (Plan Status): `Plan-Skipped | Plan-Lite | Plan-Full`.
- Evidence of files/methods/signatures validated.
- Module constraints recognized.
- 项目规范来源 (Project Rule Sources): discovered/read project rule files.
- 项目规范缓存状态 (Project Rule Cache Status): `hit/miss/reload` and reason.

### Conditional (Triggered)
- 计划摘要 (Plan Summary): required when `Plan-Lite/Plan-Full`.
- 跳过原因 (Plan Skip Reason): required when `Plan-Skipped`.
- Plan-Full 落库选项 (Plan-Full Persistence): `Display-Only | Display-And-Persist` when `Plan-Full`.
- Plan-Full 落库命名 (Plan-Full Persistence Naming): when persisted, must use `docs/plans/{topic}-{yyyyMMdd-HHmm}-plan.md`.
- 项目交付清单来源 (Project Delivery Checklist Sources): checklist files/headings read, or `none found`.
- 版本基线 (Version Baseline): discovered Java/Spring Boot baseline from current project.
- 版本基线证据 (Version Baseline Evidence): file path + key/value source used for baseline discovery.
- MySQL 基线 (MySQL Baseline): discovered MySQL baseline from project-visible sources or `unknown`.
- MySQL 基线证据 (MySQL Baseline Evidence): file path/config key/doc source for MySQL baseline.
- ES 场景声明 (ES Scenario Declaration): `Real-time` or `Near/Non-real-time` with rationale.
- 经验库扫描结果 (Learning Discovery): scan scope, match strategy, and Top-N cutoff.
- 命中经验卡 (Matched Learnings): matched card ids and titles.
- 经验卡契约校验 (Learning Card Contract Check): cards missing required five sections or minimal `machine_block` fields are invalid and ignored.
- 方案映射表 (Plan-to-Code Mapping): `方案条目 | 代码位置 | 验证项 | 状态`, when `Implement Mode` uses `Plan-Lite/Plan-Full`.

## 规则应用 (Rules Applied)
- 本次应用的硬约束 (Hard constraints applied in this task).
- 本次评估的软建议 (Soft suggestions considered).
- 规则冲突处理 (Rule Conflict Resolution): conflict points and adopted project-local rules.
- 已触发规则 (Activated Rules): list activated rules using `id + 中文含义 + trigger reason`.
- 未触发规则及原因 (Skipped Rules with Reason): list skipped rules using `id + 中文含义 + skip reason`.

## 验证结果 (Validation)
### Core (Always)
- 编译/静态检查状态 (Compile/static validation status).
- 定向测试/验证状态 (Test/verification status).
- 主要改动点 (Main Changes): touched modules/files, intended behavior changes, and protected paths intentionally unchanged when relevant.
- 影响面与回归点 (Change impact and regression points).
- 项目交付清单符合情况 (Project Delivery Checklist Fit): when a project checklist exists.
- 交付决策提示 (Post-Code Delivery Prompt): when code changed.

### Conditional (Triggered)
- 计划映射回填 (Plan Mapping Backfill): when `Plan-Lite/Plan-Full`, report per-item `done/partial/deferred` and reason.
- Plan-Full 落库结果 (Plan-Full Persistence Result): examples: `display-only`, `persisted -> <path>`, `persist-failed -> <path> -> <reason>`.
- 外部调用护栏 / 外部调用例外: when `external_call_guardrails` is triggered.
- 数据库查询边界: when `db_query_bounds` is triggered.
- 入参有效性说明: when `input_validity_baseline` is triggered.
- 字段链路覆盖说明: when `sql_field_coverage` is triggered.
- 批量策略证据: when `batch_policy` is triggered.
- MyBatis 变更安全: when `mybatis_mutation_safety` is triggered.
- MyBatis WHERE 确定性: when `mybatis_where_determinism` is triggered.
- 复用与封装说明: when `reuse_encapsulation` is triggered.
- 无关改动报告: when `unrelated_change_control` is triggered.
- 版本兼容性检查: when `version_alignment` is triggered.
- MySQL 兼容性检查: when `mysql_version_alignment` is triggered.
- ES 场景检查: when `es_scenario_alignment` is triggered.
- 经验应用检查 / 经验动作映射: when `learning_recall_alignment` is triggered.

## 检查清单 (Checklist)
| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| 核心-构建与编译 (Core: Build & Compile) | PASS/FAIL/N-A | Hard | 构建命令输出或说明 | 修复动作或 `none` |
| 核心-定向测试与验证 (Core: Targeted Test/Verification) | PASS/FAIL/N-A | Hard | 测试名/命令/输出或说明 | 修复计划或 `none` |
| 核心-项目规范一致性 (Core: Project Rule Alignment) | PASS/FAIL/N-A | Hard | 已读取项目规范与冲突处理记录 | 修正规则采用或 `none` |
| 核心-无关改动控制 (Core: Unrelated Change Control) | PASS/FAIL/N-A | Hard | 无关改动披露或 `none` | 补齐披露或回滚无关改动 |
| 核心-可维护性说明 (Core: Maintainability Notes) | PASS/FAIL/N-A | Soft | 复用/封装证据或说明 | 重构跟进或 `none` |
| 条件-数据变更安全 (Conditional: Data Mutation Safety) | PASS/FAIL/N-A | Hard | 仅触发时填写 MyBatis/SQL 证据 | 安全修复或 `none` |
| 条件-批量策略合规 (Conditional: Batch Strategy Compliance) | PASS/FAIL/N-A | Hard | 仅触发时填写批量策略证据 | 批量改造或 `none` |
| 条件-版本对齐合规 (Conditional: Version Alignment Compliance) | PASS/FAIL/N-A | Hard/Soft | 仅触发时填写版本兼容证据；未触发写 skipped 理由 | 对齐版本实现或 `none` |
| 条件-MySQL版本对齐合规 (Conditional: MySQL Version Alignment Compliance) | PASS/FAIL/N-A | Hard/Soft | 仅触发时填写 MySQL 版本兼容证据；未触发写 skipped 理由 | 对齐 SQL/DDL 或 `none` |
| 条件-ES场景一致性合规 (Conditional: ES Scenario Alignment Compliance) | PASS/FAIL/N-A | Hard/Soft | 仅触发时填写 ES 场景声明与一致性/延迟证据 | 修正场景实现或 `none` |
| 条件-经验回流应用合规 (Conditional: Learning Recall Alignment Compliance) | PASS/FAIL/N-A | Hard/Soft | 仅触发时填写命中经验卡的采用/延期证据 | 应用经验卡动作或 `none` |

## 风险说明 (Risk Notes)
- Remaining risks.
- Deferred optimizations or suggestions.
```

## Review-Only Output
For `Review-Only Mode`, append one required section:

```markdown
## 审查结论 (Review Verdict)
- Blocking: blocking findings list.
- Non-blocking: non-blocking findings list.
- Observations: informational observations.
- Go/No-Go: final gate decision.
```

Verdict consistency gate:
- If `Blocking` is non-empty, `Go/No-Go` must be `No-Go`.
- If the verdict is inconsistent, correct it before completion.

## Output Noise Rules
- Emit only core fields and triggered conditional fields.
- Do not emit repeated `N-A` rows for untriggered conditional rules unless explicit audit completeness is requested.
- Keep full conclusions in `Validation`; keep `Checklist` evidence short and referential.
- Do not emit `Matched/Applied/Deferred Learnings` when no learning card matched.
