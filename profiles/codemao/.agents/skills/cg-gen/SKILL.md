---
name: cg-gen
description: Generate, modify, plan, or review Java/Kotlin backend code with mixed enforcement (hard constraints + soft suggestions). Use for Java/Kotlin backend service/API/mapper/repository/config/bugfix tasks, review-only backend code checks, codegen-min-spec compatibility triggers, and tasks that provide cg-req RequirementContext.
---

# cg-gen

## Goal
Apply the minimum non-negotiable specification for Java/Kotlin backend implementation, planning, and review.
Prevent unsafe assumptions, hidden regressions, unbounded data access, unsafe mutations, and unsupported framework/database usage while keeping user prompts simple.

## User Prompt Contract
Users should be able to trigger this skill with one short sentence.

Preferred prompts:
- `使用 $cg-gen 实现：新增用户分页查询接口`
- `使用 $cg-gen 审查当前后端改动`
- `使用 $cg-gen 实现：只改 service 和 mapper，不改接口协议`
- `使用 $cg-gen 基于以下 RequirementContext 生成方案/实现：...`

The user does not need to name DB, MyBatis, external-call, version, checklist, or learning-card rules. Infer and activate those rules from the task and repository evidence.

## Trigger And Scope
Trigger this skill in either mode:
- Explicit trigger: User asks to use `cg-gen`, `$cg-gen`, `codegen-min-spec`, or `$codegen-min-spec`.
- Implicit trigger: User asks for Java/Kotlin backend service/API/mapper/repository/config code generation, code modification, refactoring, or bugfix work.
- Explicit review trigger: User asks for backend `已有代码审查`, `代码评审`, `review`, or `review-only`.
- Requirement trigger: User provides structured `RequirementContext` from `cg-req`.

Apply this skill to:
- Java/Kotlin backend implementation tasks.
- Existing Java/Kotlin backend changes and new code additions.
- Backend technical planning/design tasks that may feed implementation.
- Review-only checks for Java/Kotlin backend changes.

Do not apply this skill as frontend/UI-specific guidance.

## Response Language
Use Chinese as the default narrative language.
Keep canonical identifiers in English where they are part of the contract, for example `Pre-check`, `Trigger Profile`, `Risk Notes`, and `Review-Only Mode`.

## Default Behavior
- Select `Review-Only Mode` when the user explicitly asks to review, audit, or avoid code changes.
- Select `Implement Mode` when the user asks to implement, generate, modify, refactor, or fix backend code.
- Select `Plan-Skipped` for tiny scoped changes or direct-implementation requests.
- Select `Plan-Lite` for normal implementation when useful.
- Recommend `Plan-Full` for high-risk, cross-module, DB-write, external-call, schema/data mutation, ES, or broad requirement-design work.
- Classify ambiguous risk upward.
- Keep output compact by default; load [references/output-contracts.md](references/output-contracts.md) for detailed output requirements.
- For Plan-Full and post-code delivery interactions, load [references/planning-and-delivery.md](references/planning-and-delivery.md).
- For `RequirementContext` / `SolutionContext` handling, load [references/cg-req-intake.md](references/cg-req-intake.md).
- Load [references/cases.md](references/cases.md) only when concrete examples or forward-validation cases are needed.

## Enforcement Model
Use mixed enforcement:
- Hard constraints: Block progress when violated. Report exact missing checks or failed gates.
- Soft suggestions: Continue, but record residual risk in `Risk Notes`.
- Hard gates apply only to activated hard rules; unactivated hard rules do not block.
- Project-local rules override this generic skill when conflict exists; record the adopted project rule in detailed output.

## Workflow
Run this demand-driven sequence:
1. Select mode: `Implement Mode` or `Review-Only Mode`.
2. Select plan state: `Plan-Skipped`, `Plan-Lite`, or `Plan-Full`.
3. Classify `Trigger Profile`: `L0-Review`, `L1-Small`, `L2-Standard`, or `L3-HighRisk`.
4. Activate only relevant rules from the Rule Activation Matrix.
5. Complete required pre-checks before implementation or review conclusion.
6. Modify only the request-related minimum scope in `Implement Mode`.
7. Run post-validation and checklist gates before declaring completion.
8. Use compact output unless detailed output is required.

## Trigger Profile
- `L0-Review`: Review-only task, no code modification.
- `L1-Small`: Small implementation scope; no DB, no external HTTP call, no MyBatis mutation/XML `WHERE` structure touch.
- `L2-Standard`: Normal implementation; may touch DB query bounds or external HTTP call guardrails.
- `L3-HighRisk`: High-risk implementation; includes schema/data mutation, batch mutation, MyBatis `delete`/`update`, MyBatis XML `WHERE` structure, ES path, or cross-module changes.

If the profile is ambiguous, choose the higher-risk profile.

## Rule Activation Matrix
Use this matrix to decide which rules are active in the current task.

| id | trigger_condition | severity | required_evidence | na_policy |
| --- | --- | --- | --- | --- |
| `core_precheck` | Always | Hard | File/method/signature/module-boundary evidence | Not allowed |
| `plan_mapping` | `Implement Mode` and `Plan-Lite/Plan-Full` selected | Hybrid | `方案映射表` rows complete | `Plan-Skipped` -> `N-A(with reason)` |
| `plan_full_persistence` | `Implement Mode` and `Plan-Full` selected | Soft | Persistence option decision + evidence | Missing -> wait for user selection |
| `project_rule_discovery` | First run in repo or project-rule files changed | Hard | Sources read + precedence decision | Reuse cache allowed when unchanged |
| `version_alignment` | Spring API/dependency/config/MyBatis-Spring integration touched | Hybrid | Version baseline + compatibility proof + fallback decision | Skip when not touched |
| `mysql_version_alignment` | MySQL DDL/index/dialect/pagination-sorting/JSON-fulltext features touched | Hybrid | MySQL baseline + compatibility proof + fallback decision | Skip when not touched |
| `es_scenario_alignment` | ES index/write/read/aggregation/sync path touched | Hybrid | Scenario declaration + consistency/latency budget + implementation evidence | Skip when not touched |
| `learning_recall_alignment` | Five-section learning cards + minimal `machine_block` matched from `docs/rule/codegen-learnings` | Hybrid | Matched list + adopted/deferred reasons + risk for deferral | Skip when no matched cards |
| `project_delivery_checklist` | Project-local post-code checklist/delivery checklist exists | Soft | Checklist source + conforming/non-conforming items + user decision for fixes | Skip when no checklist found |
| `unrelated_change_control` | Any code modification | Hard | `Reason/Scope/Risk/Rollback Hint` when unrelated changes exist | `none` if no unrelated changes |
| `sql_field_coverage` | New DB field added | Soft | Coverage matrix (migration/entity/mapper/xml) | Skip when not touched |
| `batch_policy` | Batch requirement or batch write path | Hard | Batch implementation evidence or exception (`reason/risk/expiry`) | Skip when not touched |
| `reuse_encapsulation` | Repeated equivalent flow `>=2` in same module | Soft | Reuse detection and decision notes | Skip when not touched |
| `external_call_guardrails` | External HTTP call added/modified | Hard | Timeout + pool evidence or exception record | Skip when not touched |
| `db_query_bounds` | DB read query added/modified | Hard | `limit`/pagination/max-page proof or exemption proof | Skip when not touched |
| `mybatis_mutation_safety` | MyBatis `delete`/`update` added/modified | Hard | Explicit `WHERE` evidence | Skip when not touched |
| `mybatis_where_determinism` | MyBatis XML `WHERE` structure touched | Hard | Deterministic structure evidence | Skip when not touched |
| `input_validity_baseline` | Input handling touched | Soft | Baseline check and exception notes | Skip when not touched |
| `post_validation` | Any implementation/review output | Hard | Validation summary and activated hard-evidence fields | Not allowed |
| `post_delivery_decision` | `Implement Mode` after code changes and validation summary | Soft | User-facing change list + documentation/test-point decision prompt | Skip for Review-Only or no code change |
| `checklist_core` | Always | Hard/Soft | Core checklist rows | Not allowed |
| `checklist_conditional` | Triggered dimensions only | Hard/Soft | Conditional checklist rows for activated dimensions | Do not emit for untriggered dimensions |

## Pre-Check
Complete these checks before writing code or finishing review:
- Read real implementation files before calling existing methods. Do not assume a method exists.
- Confirm method signatures: method name, parameter types, return type, visibility, and visible nullability contract.
- Identify module boundaries, layering, dependency direction, naming conventions, and existing style.
- Identify the smallest safe change set required by the request.
- Discover project rules from `.mdc`, `.cursorrules`, `README.md`, `AGENTS.md`, and `CLAUDE.md`; reuse session cache only when sources are unchanged.
- Search project-local docs/rules for post-code checklists or delivery checklists using likely names/headings such as `checklist`, `交付清单`, `检查清单`, `验收清单`, `提测`, `上线`, `交付`, and `发布`.
- Discover Java/Spring Boot baseline from Gradle/Maven build files for backend implementation/review tasks.
- Discover MySQL baseline only when MySQL-related technical surfaces are touched; if unknown, use conservative implementation and record the source gap.
- Declare ES scenario (`Real-time` or `Near/Non-real-time`) when ES is touched.
- Scan `docs/rule/codegen-learnings` for matched five-section learning cards before implementation/review conclusion.

Learning cards are valid only when they include:
- `## 场景 (Scenario)`
- `## 核心约束 (The Golden Rule)`
- `## 验证守卫 (Verification Gate)`
- `## 风险预警 (Anti-Patterns)`
- `### AI 提示词适配建议`
- A trailing minimal `machine_block` with `id`, `trigger_signals.keywords[]`, `problem_pattern`, and `recommended_actions[]`.

Match learning cards by `machine_block` keywords/problem pattern first, then by section-derived trigger/problem/action. Load only Top-N matched cards, default N=3.

If any activated hard pre-check is missing, stop and report blockers.

## Implementation Rules
Apply these constraints while editing code:
- Change only request-related minimum scope.
- Do not make unrelated logic, formatting-only, or metadata edits.
- If unrelated changes are unavoidable, record `Reason`, `Scope`, `Risk`, and `Rollback Hint`; missing disclosure is a hard failure.
- Follow existing code style and naming conventions in the touched module.
- Preserve explicit error handling and null-safety behavior.
- Keep logging semantically useful; avoid noisy or misleading logs.
- Do not introduce unverified implicit behavior changes.

Hard implementation constraints:
- Batch requirement or batch write path: use batch SQL or dedicated batch processing interfaces by default; looping single-item writes is not allowed unless requirements explicitly permit a small-batch exception with `reason`, `risk`, and `expiry`.
- External HTTP calls (`okhttp`, `RestTemplate`, `WebClient`, Feign, or equivalent): require connect/read timeout, write timeout when supported, and verifiable connection-pool or transport policy. Framework-managed exceptions require `reason`, `risk`, compensating controls, and `expiry`.
- DB read queries: do not add unbounded full-scan reads as the default path; enforce `limit` or pagination and a traceable maximum page size. Primary-key/unique-key single-row lookups, `exists`, `count`, and naturally bounded aggregations may be exempt with proof.
- MyBatis `delete`/`update`: require explicit `WHERE`.
- MyBatis XML `WHERE` structure: keep condition structure deterministic and parameterized; do not dynamically add/remove `WHERE` conditions with `if`/`trim`/`choose`.
- Version alignment: when touching Spring APIs, dependencies, config keys, or MyBatis-Spring integration, provide Java/Spring Boot baseline-compatible evidence and fallback decision.
- MySQL alignment: when touching DDL, indexes, dialect-sensitive SQL, pagination/sorting semantics, JSON/fulltext, or charset/collation-sensitive behavior, provide MySQL baseline-compatible evidence and fallback decision.
- ES alignment: when touching ES index/write/read/aggregation/sync path, scenario declaration and implementation evidence must match.
- Hard learning cards: adopt matched hard recommendations or provide explicit counter-evidence.

Soft implementation constraints:
- SQL field additions should cover migration/entity/mapper/xml; missing links go to `Risk Notes`.
- Equivalent workflow fragments repeated 2+ times in the same module should trigger reuse/extraction notes or a deferral reason.
- Input handling should treat business inputs as non-null/non-blank and identifier-like numeric fields as non-zero unless requirements explicitly permit exceptions.
- Non-identifier numeric values such as amount, count, and offset are not automatically subject to the non-zero rule.

## Post-Validation And Checklist
After code changes or review output:
- Ensure compile/static checks pass at least to a compilable state for touched modules, or report exact blockers.
- Provide tests or executable verification steps for the critical path.
- Summarize main changes, impact, and regression points.
- Provide evidence only for activated hard rules; do not require evidence for skipped rules.
- Run core checklist items before declaring completion.

Core checklist items:
- `Build & Compile` (Hard)
- `Targeted Test/Verification` (Hard)
- `Project Rule Alignment` (Hard)
- `Unrelated Change Control` (Hard)
- `Maintainability Notes` (Soft)

Conditional checklist items are emitted only for activated dimensions:
- `Data Mutation Safety` (Hard)
- `Batch Strategy Compliance` (Hard)
- `Version Alignment Compliance` (Hard/Soft)
- `MySQL Version Alignment Compliance` (Hard/Soft)
- `ES Scenario Alignment Compliance` (Hard/Soft)
- `Learning Recall Alignment Compliance` (Hard/Soft)

Any hard checklist row with `FAIL` blocks completion. Soft `FAIL` rows are allowed only when tracked in `Risk Notes` with a follow-up action.

## Output Policy
Default to compact completion output after successful implementation. Do not print full `Pre-check`, `Rules Applied`, or `Checklist` by default.

Print or load the detailed output contract when:
- the user asks for detailed/audit/checklist output,
- a hard gate fails,
- `Review-Only Mode` is selected,
- `Plan-Full` requires an explicit persistence decision,
- compliance-sensitive work needs visible evidence, such as DB mutation safety, external-call guardrails, version compatibility, MySQL compatibility, or ES consistency.

`Rules Applied` uses this unified policy:
- Default compact output: omit the full section.
- Detailed audit, Review-Only, hard-gate failure, or compliance-sensitive output: include activated/skipped rules and conflict resolution.
- Learning details are shown only when `learning_recall_alignment` is triggered or detailed audit is requested.

## Violation Handling
- Hard-constraint violation: Stop execution, list exact missing checks or failed gates, and ask to resolve them first.
- Soft-constraint violation: Continue, but record the unresolved item in `Risk Notes`.
- `Implement Mode` + `Plan-Lite/Plan-Full`: incomplete plan-to-code mapping is a hard failure.
- `Implement Mode` + `Plan-Skipped`: allowed, but disclose skip reason and residual risk in `Risk Notes`.
- `Review-Only Mode`: if `Blocking` findings exist while `Go/No-Go` is not `No-Go`, treat the verdict as inconsistent and fix the decision before completion.
- Any unrelated change without full disclosure is a hard failure.

## Reference Usage
- Load [references/planning-and-delivery.md](references/planning-and-delivery.md) for Plan-Full persistence, plan-to-code mapping, and post-code delivery decisions.
- Load [references/output-contracts.md](references/output-contracts.md) for compact completion, detailed audit, checklist, and review verdict templates.
- Load [references/cg-req-intake.md](references/cg-req-intake.md) when the user provides `RequirementContext` or asks for a solution/technical plan.
- Load [references/cases.md](references/cases.md) only when concrete trigger/enforcement examples are needed.

## Project Adapter Placeholder
Do not enable project-specific rules by default.
When adding a project adapter, append an adapter section in a reference file with activation conditions, additional hard constraints, additional soft suggestions, and adapter validation checks.
