---
name: cg-gen
description: Generate or modify backend Java/Kotlin code with mixed enforcement (hard constraints + soft suggestions), and apply matched five-section learning cards from docs/rule/codegen-learnings.
---

# cg-gen

## Goal
Apply the minimum non-negotiable specification for Java/Kotlin backend code generation and code modification.
Prevent unsafe assumptions, reduce hidden regressions, and keep output consistently reviewable.

## Trigger And Scope
Trigger this skill in either mode:
- Explicit trigger: User asks to use `cg-gen`, `$cg-gen`, `codegen-min-spec`, or `$codegen-min-spec`.
- Implicit trigger: User asks to write code, modify code, add service/API methods, refactor code, or fix backend bugs.
- Explicit review trigger: User asks for `已有代码审查`, `代码评审`, `review`, or `review-only`.

Apply this skill to:
- Backend Java/Kotlin implementation tasks.
- Existing code changes and new code additions.
- Tasks that already provide structured requirement intake output from `cg-req` (`RequirementContext`).

Do not treat this skill as frontend/UI-specific guidance.

## Enforcement Model
Use mixed enforcement:
- Hard constraints: Block progress when violated. Return the missing items and fix them before continuing.
- Soft suggestions: Allow progress. Record residual risk in `Risk Notes`.

## Response Language
Use Chinese as the default response language for all narrative content.
Keep fixed section identifiers and checklist field names compatible by using bilingual headers when needed.
Preferred style:
- Chinese primary text.
- Keep canonical identifiers in parentheses for traceability (for example: `预检查 (Pre-check)`).

## Workflow
Run a lightweight, demand-driven sequence:
- First classify task risk with `Trigger Profile`.
- Then activate only relevant rules from `Rule Activation Matrix`.
- Keep hard gates for activated hard rules only.

### 0) Mode Selection
Select one mode before execution:
- `Implement Mode`: generate or modify code with the full implementation workflow.
- `Review-Only Mode`: do not modify code; produce structured review output and gate decision.

### 0.5) Trigger Profile (Risk Tier)
Classify the task into one profile before pre-check:
- `L0-Review`: Review-only task, no code modification.
- `L1-Small`: Small implementation scope; no DB, no external HTTP call, no MyBatis mutation/XML `WHERE` structure touch.
- `L2-Standard`: Normal implementation; may touch DB query bounds or external HTTP call guardrails.
- `L3-HighRisk`: High-risk implementation; includes schema/data mutation, batch mutation, MyBatis `delete`/`update`, MyBatis XML `WHERE` structure, or cross-module changes.

If profile is ambiguous, choose the higher-risk profile.

### 0.6) Rule Activation Matrix
Use this matrix to decide which rules are active in the current task.

| id | trigger_condition | severity | required_evidence | na_policy |
| --- | --- | --- | --- | --- |
| `core_precheck` | Always | Hard | File/method/signature/module-boundary evidence | Not allowed |
| `plan_mapping` | `Implement Mode` with plan-driven request | Hard | `方案映射表` rows complete | Not allowed when required |
| `project_rule_discovery` | First run in repo or project-rule files changed | Hard | Sources read + precedence decision | Reuse cache allowed when unchanged |
| `version_alignment` | Spring API/dependency/config/MyBatis-Spring integration touched | Hybrid | Version baseline + compatibility proof + fallback decision | Skip when not touched |
| `mysql_version_alignment` | MySQL DDL/index/dialect/pagination-sorting/JSON-fulltext features touched | Hybrid | MySQL baseline + compatibility proof + fallback decision | Skip when not touched |
| `es_scenario_alignment` | ES index/write/read/aggregation/sync path touched | Hybrid | Scenario declaration + consistency/latency budget + implementation evidence | Skip when not touched |
| `learning_recall_alignment` | Five-section learning cards + minimal `machine_block` matched from `docs/rule/codegen-learnings` | Hybrid | Matched list + adopted/deferred reasons + risk for deferral | Skip when no matched cards |
| `unrelated_change_control` | Any code modification | Hard | `Reason/Scope/Risk/Rollback Hint` when unrelated changes exist | `none` if no unrelated changes |
| `sql_field_coverage` | New DB field added | Soft | Coverage matrix (migration/entity/mapper/xml) | Skip when not touched |
| `batch_policy` | Batch requirement or batch write path | Hard | Batch implementation evidence or exception (`reason/risk/expiry`) | Skip when not touched |
| `reuse_encapsulation` | Repeated equivalent flow `>=2` in same module | Soft | Reuse detection and decision notes | Skip when not touched |
| `external_call_guardrails` | External HTTP call added/modified | Hard | Timeout + pool evidence or exception record | Skip when not touched |
| `db_query_bounds` | DB read query added/modified | Hard | `limit`/pagination/max-page proof or exemption proof | Skip when not touched |
| `mybatis_mutation_safety` | MyBatis `delete`/`update` added/modified | Hard | Explicit `WHERE` evidence | Skip when not touched |
| `mybatis_where_determinism` | MyBatis XML `WHERE` structure touched | Hard | Deterministic structure evidence | Skip when not touched |
| `input_validity_baseline` | Input handling touched | Soft | Baseline check and exceptions notes | Skip when not touched |
| `post_validation` | Any implementation/review output | Hard | Validation summary and activated hard-evidence fields | Not allowed |
| `checklist_core` | Always | Hard/Soft | Core checklist rows | Not allowed |
| `checklist_conditional` | Triggered dimensions only | Hard/Soft | Conditional checklist rows for activated dimensions | Do not emit for untriggered dimensions |

### 1) Pre-Check (Hard Constraints)
Complete these checks before writing code:
- Read real implementation files before calling existing methods. Do not assume a method exists.
- Confirm method signatures: method name, parameter types, return type, visibility, nullability contract when visible.
- Identify module boundaries: layering, dependency direction, naming conventions, and existing style.
- Identify the smallest safe change set required by the request.
- Split pre-check into:
  - `Core Pre-check`: always required.
  - `Conditional Pre-check`: only for activated rules from matrix.
- In `Implement Mode`, provide a plan-to-code mapping table:
  - `方案条目 | 代码位置 | 验证项 | 状态`
  - If any required plan item is missing from mapping, treat as hard failure and block completion.
- Run project rules discovery before generation/review:
  - Check whether project-local rule files exist: `.mdc`, `.cursorrules`, `README.md`, `AGENTS.md`, `CLAUDE.md`.
  - Record the discovered and read rule sources as `项目规范来源 (Project Rule Sources)`.
  - Prefer session cache for the same repo:
    - If already read in current session and no rule-source file changed, reuse cached discovery result.
    - Force re-read only on first run or when any rule-source file changes.
- Apply rule precedence:
  - Project-local rules override this generic skill when conflict exists.
  - If conflict exists, record conflict point and adopted project rule in `规则冲突处理 (Rule Conflict Resolution)`.
- Run Version Baseline Discovery when task includes implementation or review of backend code:
  - Read Java/Spring Boot baseline from Gradle/Maven build files.
  - Record `版本基线 (Version Baseline)` and `版本基线证据 (Version Baseline Evidence)` with file path + key.
  - Do not hardcode project constants in this skill; always discover from current project.
- Run MySQL Baseline Discovery when MySQL-related implementation is touched:
  - Read MySQL version/baseline from project-visible configs/docs.
  - If baseline cannot be found, mark as `unknown` and require conservative implementation or explicit source gap note.
  - Record `MySQL 基线 (MySQL Baseline)` and `MySQL 基线证据 (MySQL Baseline Evidence)`.
- Run ES Scenario Declaration when ES is touched:
  - Declare `Real-time` or `Near/Non-real-time` before implementation/review conclusion.
  - Record `ES 场景声明 (ES Scenario Declaration)` with rationale.
- Run Learning Discovery before implementation/review conclusion:
  - Scan `docs/rule/codegen-learnings` only.
  - Parse five-section learning cards:
    - `## 场景 (Scenario)`
    - `## 核心约束 (The Golden Rule)`
    - `## 验证守卫 (Verification Gate)`
    - `## 风险预警 (Anti-Patterns)`
    - `### AI 提示词适配建议`
  - Parse minimal `machine_block`:
    - `id`
    - `trigger_signals.keywords[]`
    - `problem_pattern`
    - `recommended_actions[]`
  - `machine_block` source constraint:
    - consume the trailing block after five sections.
    - do not require or rely on frontmatter `machine_block`.
  - Match order:
    - First use `machine_block.trigger_signals.keywords` and `problem_pattern` when present.
    - Then extract trigger/problem/action from sections:
      - trigger: from scenario nouns/keywords + golden-rule constraints.
      - problem: from scenario problem description.
      - action: from golden-rule/verification-gate executable rules.
    - Then keyword match first, semantic assist second.
  - Load only Top-N matched cards (default N=3) to avoid context bloat.
  - Record `经验库扫描结果 (Learning Discovery)` and `命中经验卡 (Matched Learnings)`.

If any required pre-check is missing, stop and report blocking items.

### 2) Implementation Rules (Hard Constraints + Soft Input Baseline)
Apply these constraints while editing code:
- Change only request-related minimum scope. Avoid unrelated edits.
- Do not modify code unrelated to the current task (including unrelated file edits, logic edits, and formatting-only noise).
- If unrelated changes are unavoidable (for example: build blocker or coupled legacy defect), record:
  - `Reason`
  - `Scope`
  - `Risk`
  - `Rollback Hint`
- Missing disclosure for unrelated changes is a hard failure.
- Follow existing code style and naming conventions in the touched module.
- Preserve explicit error handling and null-safety behavior.
- Keep logging semantically useful. Avoid noisy or misleading logs.
- Do not introduce unverified implicit behavior changes.

Apply SQL field addition coverage (Soft) when adding new DB fields:
- Check migration / entity / mapper / xml as a four-part coverage chain.
- Record any missing links in `Risk Notes`; do not block completion.

Apply batch operation policy (Hard) for batch requirements:
- Use batch SQL or batch processing interfaces by default.
- Do not implement default batch behavior by looping single-item write calls.
- Allow small-batch exceptions only when requirements explicitly permit it.
- Record exception fields in `Validation`: `reason`, `risk`, and `expiry`.
- If exception record is incomplete, treat as hard-constraint failure.

Apply reuse and encapsulation guidance (Soft):
- When equivalent workflow fragments appear in 2 or more places in the same module, suggest extracting a reusable method/component.
- Record deferral decisions in `Risk Notes`.

Apply third-party HTTP call guardrails (Hard) when adding or modifying external calls (`okhttp`, `RestTemplate`, or equivalent):
- Configure and use `connect timeout`.
- Configure and use `read timeout`.
- Configure and use `write timeout` when the client supports it.
- Configure at least one verifiable connection-pool policy (for example: max connections, idle connections, keep-alive/TTL).

External call hard-constraint exceptions (Hard process):
- Allow exceptions only for low-frequency admin tasks, one-off migration scripts, or framework-managed clients where direct pool control is unavailable.
- Record exception fields in `Validation`: `reason`, `risk`, `compensating controls` (for example: retry/circuit-breaker/isolation), and `expiry`.
- If exception record is incomplete, treat as hard-constraint failure.

Apply database query bounds (Hard) when adding or modifying DB reads:
- Do not implement unbounded full-scan reads as the default path.
- Enforce `limit` or pagination (`page`/`size`) in query interfaces.
- Define and enforce a maximum page size that is traceable in code or config.
- For batch/export scenarios, document chunking strategy.

Apply MyBatis mutation safety (Hard) when writing MyBatis `delete`/`update`:
- Require an explicit `WHERE` clause.
- Block completion if `WHERE` is missing.

Apply MyBatis WHERE determinism (Hard) when writing MyBatis XML statements:
- Keep `WHERE` condition structure deterministic and parameterized.
- Do not dynamically add or remove `WHERE` conditions with `if`/`trim`/`choose`.
- Allow parameter value changes, but do not allow condition-structure changes.

DB hard-constraint exemptions:
- Primary-key or unique-key single-row lookup.
- `exists` and `count` queries.
- Aggregation queries with a natural upper bound.
- For exemptions, record `exemption reason` and `bound proof` in `Validation`.

Apply input validity baseline (Soft):
- Unless explicitly stated otherwise, treat business inputs as non-null and non-blank, and treat numeric identifiers (`id`/`key`/`code` fields) as non-zero.
- Do not apply the non-zero rule by default to non-identifier numerics (for example: amount, count, offset).
- Allow explicit exceptions when requirements clearly permit nullable or zero values.
- Record unmet baseline checks in `Risk Notes`; do not block completion.

Apply version alignment rule (Hybrid):
- Hard mode activation:
  - When touching Spring framework APIs, starter/dependency declarations, configuration keys/properties, or MyBatis-Spring integration patterns.
  - Must provide compatibility evidence aligned to current Java/Spring Boot baseline:
    - Official versioned docs/changelog notes, or
    - Existing project-supported usage pattern, or
    - Dependency-management constraints from build files/BOM.
  - Must include fallback decision when risk exists (for example: keep old API/use compatibility adapter/defer upgrade).
  - Missing compatibility evidence is a hard failure.
- Soft mode (non-framework business logic changes):
  - Mark as skipped/low-risk with reason.
  - Do not block completion.

Apply MySQL version alignment rule (Hybrid):
- Hard mode activation:
  - When touching MySQL DDL, index design, dialect-sensitive SQL, pagination/sorting semantics, JSON/fulltext features, or charset/collation-sensitive behavior.
  - Do not use MySQL features incompatible with discovered baseline without explicit compatibility explanation.
  - Provide baseline compatibility evidence and fallback decision (for example: compatible SQL rewrite/degrade path).
  - Missing compatibility evidence is a hard failure.
- Soft mode (MySQL untouched):
  - Mark as skipped with reason; do not block.

Apply ES scenario alignment rule (Hybrid):
- Hard mode activation:
  - When touching ES index/write/read/aggregation/sync path.
  - Must declare scenario: `Real-time` or `Near/Non-real-time`.
  - For `Real-time`, provide write-read visibility strategy and latency target evidence.
  - For `Near/Non-real-time`, provide async sync path, retry/idempotency, delay budget, and compensation strategy evidence.
  - Implementation must match declared scenario; mismatch is a hard failure.
- Soft mode (ES untouched):
  - Mark as skipped with reason; do not block.

Apply learning recall alignment rule (Hybrid):
- Soft mode (default):
  - For matched cards, adopt or defer each item with explicit reason.
  - Deferral is allowed but must be recorded in `Risk Notes`.
- Hard mode (card-level upgraded):
  - If a matched card is marked `hard` and no adoption/counter-evidence is provided, block completion.

### 3) Post-Validation (Hard Constraints)
Complete these validations after code changes:
- Ensure compile/static checks pass at least to a compilable state for touched modules.
- Provide tests or executable verification steps for the critical path.
- Provide change impact and regression points in the validation summary.
- Provide evidence for external call guardrails when external HTTP calls are touched.
- Provide evidence for DB query bounds when DB queries are touched.
- Provide input validity notes and explicit exceptions when input handling is touched.
- Provide evidence only for activated hard rules; do not require evidence for skipped rules.
- Provide version compatibility evidence when `version_alignment` is activated.
- Provide MySQL compatibility evidence when `mysql_version_alignment` is activated.
- Provide ES scenario evidence when `es_scenario_alignment` is activated.
- Provide learning application evidence when `learning_recall_alignment` is activated.

If a hard validation fails, stop and report unresolved blockers.

### 4) Post-Implementation Checklist (Mixed Gate)
Run this checklist before declaring completion.

Checklist execution mode:
- Hard checklist items must pass.
- Soft checklist items may fail, but must be recorded in `Risk Notes` with follow-up actions.

Core five checklist items:
- `Build & Compile` (Hard)
- `Targeted Test/Verification` (Hard)
- `Data Mutation Safety` (Hard; includes MyBatis `delete`/`update` `WHERE` and `WHERE` determinism checks when applicable)
- `Batch Strategy Compliance` (Hard)
- `Maintainability Notes` (Soft; reuse/extraction guidance and deferral notes)
- `Project Rule Alignment` (Hard)
- `Unrelated Change Control` (Hard)

Checklist row model:
- `Core Checklist Items`: always present.
- `Conditional Checklist Items (Triggered Only)`: emit only for activated dimensions; do not flood output with repetitive `N-A`.

Checklist evidence rules:
- Use `PASS` / `FAIL` / `N-A` in `Status`.
- `Status` cannot be empty.
- `N-A` is allowed only when the dimension is not touched, with a short rationale in `Evidence`.
- If a Hard item is `FAIL`, `Action` must be non-empty; otherwise treat as incomplete and block completion.

### 5) Soft Suggestions (Non-Blocking)
Provide optional but recommended improvements:
- Performance and maintainability opportunities.
- Observability opportunities (log/metric/tracing where relevant).
- Follow-up optimizations that can be deferred.

## Violation Handling
Handle violations with deterministic behavior:
- Hard-constraint violation: Stop execution, list exact missing checks or failed gates, and ask to resolve them first.
- Soft-constraint violation: Continue, but record the unresolved item in `Risk Notes`.
- Hard gates apply only to activated hard rules; unactivated hard rules do not block.
- For `version_alignment`, apply hybrid gate:
  - Activated by framework/dependency/config touch => Hard.
  - Not touched => Soft skipped note only.
- For `mysql_version_alignment`, apply hybrid gate:
  - Activated by MySQL-related technical surface touch => Hard.
  - Not touched => Soft skipped note only.
- For `es_scenario_alignment`, apply hybrid gate:
  - Activated by ES-related technical surface touch => Hard.
  - Not touched => Soft skipped note only.
- For `learning_recall_alignment`, apply hybrid gate:
  - Matched cards default to Soft with mandatory deferral risk notes.
  - Matched `hard` cards require adoption or explicit counter-evidence; otherwise block.

Mode-specific gate rules:
- `Implement Mode`: incomplete plan-to-code mapping is a hard failure.
- `Review-Only Mode`: if `Blocking` findings exist while `Go/No-Go` is not `No-Go`, treat as inconsistent verdict and block completion.
- Any unrelated change without full disclosure (`Reason/Scope/Risk/Rollback Hint`) is a hard failure.
- `mysql_version_alignment`: if activated and compatibility evidence is missing, block completion.
- `es_scenario_alignment`: if activated and scenario declaration/evidence is missing or implementation mismatches declared scenario, block completion.
- `learning_recall_alignment`: if matched `hard` learning cards are not adopted and no counter-evidence is provided, block completion.

Classify V1.1 constraints as:
- Hard: Third-party HTTP guardrails, DB query bounds, and required hard-evidence reporting.
- Soft: Input validity baseline (default non-null/non-zero) with explicit exception recording.

Classify V1.2 constraints as:
- Hard: Batch operation policy, MyBatis mutation safety, MyBatis WHERE determinism, and required hard-evidence reporting.
- Soft: SQL field addition coverage and reuse/encapsulation suggestions.

## Required Output Contract
Use this fixed output structure in responses when the skill is active.

```markdown
## 预检查 (Pre-check)
- 触发画像 (Trigger Profile): `L0-Review | L1-Small | L2-Standard | L3-HighRisk`.
- Evidence of files/methods/signatures validated.
- Module constraints recognized.
- 项目规范来源 (Project Rule Sources): discovered/read project rule files.
- 项目规范缓存状态 (Project Rule Cache Status): `hit/miss/reload` and reason.
- 版本基线 (Version Baseline): discovered Java/Spring Boot baseline from current project.
- 版本基线证据 (Version Baseline Evidence): file path + key/value source used for baseline discovery.
- MySQL 基线 (MySQL Baseline): discovered MySQL baseline from project-visible sources or `unknown`.
- MySQL 基线证据 (MySQL Baseline Evidence): file path/config key/doc source for MySQL baseline.
- ES 场景声明 (ES Scenario Declaration): `Real-time` or `Near/Non-real-time` with rationale.
- 经验库扫描结果 (Learning Discovery): scan scope, match strategy, and Top-N cutoff.
- 命中经验卡 (Matched Learnings): matched card ids and titles.
- 经验卡契约校验 (Learning Card Contract Check): cards missing required five sections or minimal `machine_block` fields are invalid and ignored.
- In `Implement Mode`, include:
  - `方案映射表 (Plan-to-Code Mapping)`
  - Columns: `方案条目 | 代码位置 | 验证项 | 状态`

## 规则应用 (Rules Applied)
- 本次应用的硬约束 (Hard constraints applied in this task).
- 本次评估的软建议 (Soft suggestions considered).
- 规则冲突处理 (Rule Conflict Resolution): conflict points and adopted project-local rules.
- 已触发规则 (Activated Rules): list activated rules using `id + 中文含义 + trigger reason`.
- 未触发规则及原因 (Skipped Rules with Reason): list skipped rules using `id + 中文含义 + skip reason`.
- 推荐展示格式 (Recommended rendering):
  - `core_precheck（核心预检查）: always`
  - `db_query_bounds（数据库查询边界）: skipped - 未触及 DB 查询`
  - `version_alignment（版本对齐）: activated - 触及 Spring 配置键`
  - `mysql_version_alignment（MySQL版本对齐）: activated - 触及 DDL/方言 SQL`
  - `es_scenario_alignment（ES场景对齐）: skipped - 未触及 ES`
  - `learning_recall_alignment（经验回流对齐）: activated - 命中 2 条经验卡`

## 验证结果 (Validation)
- 编译/静态检查状态 (Compile/static validation status).
- 定向测试/验证状态 (Test/verification status).
- 影响面与回归点 (Change impact and regression points).
- 条件输出原则（P0）:
  - 仅输出已触发规则对应的 Validation 子项。
  - 未触发规则不输出对应子项，不填充 `N-A` 占位段落。
  - `learning_recall_alignment` 未触发时，不输出 `Matched/Applied/Deferred` 相关字段。
- 已触发时按需输出子项示例：
  - `external_call_guardrails` -> 外部调用护栏 / 外部调用例外
  - `db_query_bounds` -> 数据库查询边界
  - `input_validity_baseline` -> 入参有效性说明
  - `sql_field_coverage` -> 字段链路覆盖说明
  - `batch_policy` -> 批量策略证据
  - `mybatis_mutation_safety` -> MyBatis 变更安全
  - `mybatis_where_determinism` -> MyBatis WHERE 确定性
  - `reuse_encapsulation` -> 复用与封装说明
  - `unrelated_change_control` -> 无关改动报告
  - `version_alignment` -> 版本兼容性检查
  - `mysql_version_alignment` -> MySQL 兼容性检查
  - `es_scenario_alignment` -> ES 场景检查
  - `learning_recall_alignment` -> 经验应用检查 / 经验动作映射

If any required evidence field is missing for Hard items, treat validation as incomplete and block completion.

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

Checklist gate:
- Any Hard row with `FAIL` blocks completion.
- Soft `FAIL` rows are allowed only if tracked in `Risk Notes` with follow-up action.

## 风险说明 (Risk Notes)
- Remaining risks.
- Deferred optimizations or suggestions.
```

For `Review-Only Mode`, append one required section:

```markdown
## 审查结论 (Review Verdict)
- Blocking: blocking findings list.
- Non-blocking: non-blocking findings list.
- Observations: informational observations.
- Go/No-Go: final gate decision.
```

## Project Adapter (Placeholder)
Keep this section as an extension interface for repository-specific policies. Do not enable any project-specific rule by default in this version.

When adding a project adapter in the future, append a section with this structure:

```markdown
## Project Adapter: <project-name>
### Activation
- Activation conditions.

### Additional Hard Constraints
- Project-specific hard gates.

### Additional Soft Suggestions
- Project-specific non-blocking suggestions.

### Adapter Validation
- Project-specific verification checks.
```

## Reference Usage
Load [references/cases.md](references/cases.md) when you need concrete trigger and enforcement examples.

## RequirementContext Intake (From cg-req)
When user provides a `RequirementContext` object from `cg-req`:
- Treat it as the upstream requirement source of truth for current run.
- Reuse it in `Pre-check` and `方案映射表` generation.
- Do not require re-reading original doc URL in cg-gen.
- If `fetch_status=failed`, stop and ask for requirement completion before implementation/review.
- Use plain-language terms in response:
  - `需求收集单` = `RequirementContext`
  - `开发补充单` = developer details (`本期要做/本期不做/第三方对接信息/内部改造点/验收口径`)
  - `方案设计单` = cg-gen output design package
  - `需求清单` = generic list with `背景/需求要点/需求注意事项/第三方对接/需实现部分(R*)`

### Non-Blocking Stage Advice (No Hard Gate)
- cg-gen does NOT hard-block by missing stage gate fields.
- If any recommended upstream fields are missing (for example `stage_gate`, `原始需求文件路径`, `需求收集单路径`, `需求清单路径`, `本期要做/本期不做`, developer details):
  - Continue generation.
  - Add a clear warning in `风险说明 (Risk Notes)`.
  - If `原始需求文件路径` is missing, mark this warning as high-visibility (red emphasis in markdown text).
  - Add `待补充项` list in output.
- If user explicitly asks to design only partial scope:
  - Constrain design to `本期要做`.
  - Echo `本期不做` as not in current phase.
  - If scope lists are missing, continue with best-effort assumptions and mark high risk.

### 方案设计单 (SolutionContext) Output Add-on
When current task is design/planning oriented, append a compact structured block:

```yaml
SolutionContext:
  form_label: "方案设计单"
  solution_title: string
  需求清单路径: string
  需求收集单路径: string
  原始需求文件路径: string
  需求条目映射: string[]   # format: "R1 -> 方案章节X"
  本期要做映射: string[]
  本期不做确认: string[]
  第三方依赖检查清单: string[]
  第三方对接落地清单: string[]
  复用模板清单: string[]
  接口与存储变更摘要: string[]
  风险与回滚摘要: string[]
  验收测试计划: string[]
  可开发状态: "可开发" | "带风险可开发"
  待补充项: string[]
```

Readiness rule:
- `可开发`: no blocking unknowns for implementation.
- `带风险可开发`: design can proceed but has unresolved dependency/details.

### Technical Plan Generation Rules (Generalized)
- Generate technical plan using:
  - `需求清单`
  - dialogue completion outputs (`第三方对接确认/实现范围确认/参考模板确认`)
  - repository backend technical-plan template
- In the technical plan opening section, must cite:
  - `原始需求文件路径`
  - `需求清单路径`
  - third-party source references (if any)
  - scope decision (`全量实现` or selected `R*`)
  - template references (if any)
- Items in `需实现部分` not selected in current phase must be explicitly labeled as `本期不实现`.
