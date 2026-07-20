# Codegen Min Spec Cases

## Trigger Cases

### Explicit trigger
Input:
- "使用 codegen-min-spec 生成一个新的 service 方法并补测试。"
Expected:
- Skill activates.
- Use fixed output contract.

### Implicit trigger
Input:
- "新增 service 方法并补测试。"
Expected:
- Skill activates due to coding intent.
- Enforce pre-check and post-validation hard gates.

### Trigger profile classification: L0-Review
Input:
- "已有代码审查，不要改代码。"
Expected:
- Mode = `Review-Only Mode`.
- Trigger Profile = `L0-Review`.
- No implementation mutation rules are activated.

### Trigger profile classification: L1-Small
Input:
- "在现有 service 增加一个纯内存字段转换方法并补单测，不涉及DB/外部调用。"
Expected:
- Trigger Profile = `L1-Small`.
- Skip DB/External/MyBatis hard rules with explicit reasons.
- Output keeps low-noise evidence only for activated rules.

### Trigger profile classification: L2-Standard
Input:
- "新增一个分页查询接口并补 service 校验。"
Expected:
- Trigger Profile = `L2-Standard`.
- Activate `db_query_bounds` and related validation evidence.

### Trigger profile classification: L3-HighRisk
Input:
- "新增批量更新并调整 MyBatis update 语句。"
Expected:
- Trigger Profile = `L3-HighRisk`.
- Activate batch + MyBatis hard rules and full hard evidence.

## Hard Constraint Cases

### Case 1: Method existence not verified
Input:
- Request asks to call method `findByUserId`.
- No source inspection evidence provided.
Expected:
- Block with hard-constraint violation.
- Require source read + signature confirmation.

### Case 2: Missing exception/null handling
Input:
- Generated logic ignores nullable return and unchecked exception path.
Expected:
- Mark as hard-constraint failure.
- Require fix before completion.

### Case 3: No compile/check evidence
Input:
- Code changed but no compile/static verification.
Expected:
- Block completion.
- Require verification status in `Validation`.

### Case 5: External call guardrails missing (Fail)
Input:
- Add a new `RestTemplate` integration without explicit timeout setup.
- No connection-pool policy is configured or referenced.
Expected:
- Block with hard-constraint violation.
- Return missing items list for timeout and pool evidence.

### Case 6: External call guardrails complete (Pass)
Input:
- Add an `okhttp` client call with connect/read/write timeout.
- Connection pool is configured with max/idle/keep-alive policy.
Expected:
- Pass hard constraints.
- `Validation` includes `External Call Guardrails` evidence with `value`, `unit`, `enforcement point`, and `evidence source`.

### Case 7: Unbounded DB read (Fail)
Input:
- Add repository query without `limit` or pagination.
- No max page size guard exists.
Expected:
- Block with hard-constraint violation.
- Return missing DB bounds checklist.

### Case 8: Bounded DB query with max page size (Pass)
Input:
- Add paged query with `page` and `size`.
- Enforce max page size in service or repository boundary.
Expected:
- Pass hard constraints.
- `Validation` includes `DB Query Bounds` evidence with `value`, `unit`, `enforcement point`, and `evidence source`.

### Case 11: DB natural-bound exemption (Pass)
Input:
- Add repository query `findById(id)` using primary key.
- No explicit pagination is added.
Expected:
- Pass via DB exemption.
- `Validation` records `exemption reason` and `bound proof`.

## Soft Constraint Cases

### Case 4: No performance suggestion
Input:
- Functional result is valid but no maintainability/performance note.
Expected:
- Allow completion.
- Record suggestion in `Risk Notes`.

### Case 9: Input baseline soft warning
Input:
- API input includes nullable/zero identifier path without explicit requirement support.
Expected:
- Do not block completion.
- Record input baseline warning in `Risk Notes` and `Input Validity Notes`.

### Case 10: Input baseline explicit exception
Input:
- Requirement explicitly states `parentId` may be `0` as root sentinel.
Expected:
- Allow completion.
- Record explicit exception rationale in `Input Validity Notes`.

## Equivalent Stack Coverage

### Case 12: WebClient guardrails complete (Pass)
Input:
- Add `WebClient` outbound call with connect/response timeout and pooled connector settings.
Expected:
- Pass hard constraints.
- `Validation` contains `External Call Guardrails` evidence fields (`value`, `unit`, `enforcement point`, `evidence source`).

### Case 13: WebClient guardrails missing (Fail)
Input:
- Add `WebClient` call without timeout and without pool policy evidence.
Expected:
- Block with hard-constraint violation.
- Return missing timeout/pool checklist.

### Case 14: Feign guardrails complete (Pass)
Input:
- Add Feign client with connect/read timeout configuration and verifiable pool-related transport settings.
Expected:
- Pass hard constraints.
- `Validation` records evidence fields and unmet items as `none`.

### Case 15: Feign exception path (Pass with exception record)
Input:
- Framework-managed Feign transport cannot expose pool knobs directly.
- Team uses retry + isolation with explicit risk acceptance and expiry date.
Expected:
- Pass through exception process.
- `Validation` records `reason`, `risk`, `compensating controls`, and `expiry`.

### Case 16: JPA bounded query (Pass)
Input:
- Add JPA repository method using `Pageable` and enforce max page size in service layer.
Expected:
- Pass hard constraints.
- `Validation` includes DB bound evidence fields.

### Case 17: MyBatis unbounded query (Fail)
Input:
- Add MyBatis mapper query returning full table list without `limit`/pagination.
Expected:
- Block with hard-constraint violation.
- Return DB bound missing-items list.

### Case 18: SQL field addition coverage complete (Soft Pass)
Input:
- Add a new DB field and update migration, entity, mapper, and xml consistently.
Expected:
- Do not block completion.
- `Validation` includes `SQL Field Coverage Notes` with full coverage matrix.

### Case 19: SQL field addition coverage missing links (Soft Warning)
Input:
- Add a new DB field but forget to update mapper and xml.
Expected:
- Do not block completion.
- Missing links are recorded in `Risk Notes` and `SQL Field Coverage Notes`.

### Case 20: Batch implementation via batch SQL (Hard Pass)
Input:
- Implement batch update using a batch SQL statement or dedicated batch interface.
Expected:
- Pass hard constraints.
- `Validation` includes `Batch Operation Evidence`.

### Case 21: Batch implementation by looping single writes (Hard Fail)
Input:
- Implement batch update by iterating and calling single-row update method as default path.
Expected:
- Block with hard-constraint violation.
- Return missing batch-policy checklist.

### Case 22: Small-batch exception record complete (Hard Pass With Exception)
Input:
- Requirement explicitly allows small-batch execution with risk acceptance.
- `Validation` contains `reason`, `risk`, and `expiry`.
Expected:
- Pass through exception path.
- `Batch Operation Evidence` records exception details.

### Case 23: MyBatis delete with explicit WHERE (Hard Pass)
Input:
- Add MyBatis `delete` statement with explicit `WHERE id = #{id}`.
Expected:
- Pass hard constraints.
- `MyBatis Mutation Safety` includes statement location evidence.

### Case 24: MyBatis delete without WHERE (Hard Fail)
Input:
- Add MyBatis `delete` statement without `WHERE`.
Expected:
- Block with hard-constraint violation.
- Return mutation-safety missing-items list.

### Case 25: MyBatis deterministic WHERE (Hard Pass)
Input:
- MyBatis XML uses fixed `WHERE` condition structure with parameterized values.
Expected:
- Pass hard constraints.
- `MyBatis WHERE Determinism` includes XML statement location evidence.

### Case 26: MyBatis dynamic WHERE structure (Hard Fail)
Input:
- MyBatis XML uses `if`/`trim`/`choose` to dynamically add/remove `WHERE` conditions.
Expected:
- Block with hard-constraint violation.
- Return determinism violation details.

### Case 27: Reuse suggestion for duplicate workflow fragments (Soft Warning)
Input:
- Equivalent workflow fragment appears in 2 or more places in the same module.
Expected:
- Do not block completion.
- `Reuse Notes` and `Risk Notes` record extraction suggestion or deferral decision.

## Post-Implementation Checklist Cases

### Case 28: Checklist section missing (Fail)
Input:
- Task output includes `Pre-check/Rules Applied/Validation/Risk Notes` but no `Checklist` section.
Expected:
- Treat as incomplete output contract.
- Block completion until checklist is present.

## Plan Stage Cases

### Case 62: Plan-Skipped for tiny scope (Pass, Non-Blocking)
Input:
- Implement Mode task modifies a single local mapping line with no DB/external call.
- User asks to implement directly.
Expected:
- `Plan Status = Plan-Skipped`.
- `Plan Skip Reason` is present.
- Execution continues without plan-mapping hard block.

### Case 63: Plan-Lite enabled mapping hard gate (Fail when incomplete)
Input:
- Implement Mode task touches API + service and selects `Plan-Lite`.
- `方案映射表` misses one planned item.
Expected:
- `plan_mapping` is activated.
- Completion is blocked due to incomplete mapping.

### Case 64: Upgrade recommendation not adopted (Pass with risk note)
Input:
- Trigger Profile is `L2-Standard` with DB write changes.
- User keeps `Plan-Skipped`.
Expected:
- Output includes non-blocking upgrade recommendation.
- `Risk Notes` records skip rationale and residual risk.
- Implementation is allowed to continue.

### Case 65: Plan-Full with Display-Only (Pass)
Input:
- Task selects `Plan-Full`.
- Persistence option = `Display-Only`.
Expected:
- Full plan is shown in conversation.
- No repository plan artifact is written.
- `Pre-check` records `Plan-Full Persistence = Display-Only`.

### Case 66: Plan-Full with Display-And-Persist (Pass)
Input:
- Task selects `Plan-Full`.
- Persistence option = `Display-And-Persist`.
Expected:
- Full plan is shown in conversation.
- Plan artifact is persisted to `docs/plans/` using `{topic}-{yyyyMMdd-HHmm}-plan.md`.
- `Validation` records persisted path and write status.

### Case 67: Plan-Full without asking persistence choice (Fail)
Input:
- Task enters `Plan-Full`.
- User did not pre-specify persistence option.
- Assistant shows full plan but does not ask persistence choice.
Expected:
- Treat as interaction contract violation.
- Must ask user to choose `Display-Only` or `Display-And-Persist` immediately after plan display.

### Case 68: Plan-Full with colloquial \"落库\" input (Pass)
Input:
- Task enters `Plan-Full`.
- User replies only: `落库` (or `存档`).
Expected:
- Map colloquial input to `Display-And-Persist`.
- Persist document to `docs/plans/{topic}-{yyyyMMdd-HHmm}-plan.md`.
- `Validation` includes `persisted -> <path>`.

### Case 69: Topic fallback when not inferable (Pass)
Input:
- Task enters `Plan-Full` and chooses persistence.
- Requirement topic cannot be inferred from prompt/context.
Expected:
- Use fallback topic `general-plan`.
- Filename is `docs/plans/general-plan-{yyyyMMdd-HHmm}-plan.md`.

### Case 70: Plan-Full with explicit choice in same turn (Pass)
Input:
- Task enters `Plan-Full`.
- User already provides explicit choice (`Display-Only` or `Display-And-Persist`) in the same request.
Expected:
- Assistant reuses provided choice directly.
- No extra persistence-choice question is required.

### Case 71: Plan-Full with no explicit choice after display (Pass)
Input:
- Task enters `Plan-Full`.
- User does not pre-specify persistence option.
- Assistant has already shown the full plan.
Expected:
- Assistant asks persistence choice and waits for user selection.
- Assistant does not auto-default to `Display-Only`.

### Case 72: Plan-Full persist write failure result format (Pass)
Input:
- Task enters `Plan-Full`.
- User selects `Display-And-Persist`.
- Plan persistence write fails due to path or IO error.
Expected:
- `Validation` uses standardized result:
  - `persist-failed -> <path> -> <reason>`
- Failure reason is concise and actionable.

### Case 29: Hard checklist item failed with empty action (Fail)
Input:
- `Build & Compile` row is `FAIL`, but `Action` is empty.
Expected:
- Treat checklist as incomplete.
- Block completion and require explicit action.

### Case 30: Soft checklist fail with follow-up (Pass With Risk)
Input:
- `Maintainability Notes` row is `FAIL` with concrete follow-up action.
- Same follow-up is mirrored in `Risk Notes`.
Expected:
- Allow completion.
- Keep risk tracking entry.

### Case 31: N-A rationale for untouched data mutation dimension (Pass)
Input:
- Task only changes pure in-memory utility code, no SQL/MyBatis touched.
- `Data Mutation Safety` row is `N-A` with short rationale.
Expected:
- Pass checklist gate.
- Preserve rationale in `Evidence`.

### Case 32: Checklist all hard rows pass (Pass)
Input:
- Hard rows are all `PASS`.
- Soft row is `PASS` or justified `N-A`.
Expected:
- Completion allowed.
- Output contract remains stable with fixed checklist table columns.

## Mode Selection And Plan/Review Coverage Cases

### Case 33: Implement mode with complete plan mapping (Pass)
Input:
- Request starts from approved technical plan and asks for implementation.
- `Pre-check` includes mapping table: `方案条目 | 代码位置 | 验证项 | 状态`.
Expected:
- Implement Mode applies.
- Completion allowed when hard gates pass.

### Case 34: Implement mode missing required plan mapping rows (Fail)
Input:
- Implementation request references technical plan.
- Mapping table is missing one or more required plan items.
Expected:
- Treat as hard failure.
- Block completion until mapping is complete.

### Case 35: Review-only with blocking findings and Go/No-Go = No-Go (Pass)
Input:
- Review-only request over existing code.
- Output includes `审查结论 (Review Verdict)` with non-empty `Blocking`.
- Final decision is `No-Go`.
Expected:
- Review-Only Mode applies.
- Verdict is consistent; completion of review output allowed.

### Case 36: Review-only with blocking findings but Go/No-Go != No-Go (Fail)
Input:
- Review-only request over existing code.
- Output includes `Blocking` findings but `Go/No-Go` is `Go`.
Expected:
- Treat as inconsistent verdict.
- Block completion and require decision correction.

## Project Rules Precedence And Unrelated-Change Control Cases

### Case 37: Project rule conflict resolved with project-local rule (Pass)
Input:
- Skill default guidance conflicts with `.cursorrules` or `README.md`.
- Output records conflict point and adopts project-local rule.
Expected:
- Pass hard gate.
- `规则冲突处理 (Rule Conflict Resolution)` clearly states adopted project rule.

### Case 38: Skip project rules discovery and start coding directly (Fail)
Input:
- No `.mdc/.cursorrules/README.md/AGENTS.md/CLAUDE.md` discovery evidence in `Pre-check`.
Expected:
- Treat as hard pre-check failure.
- Block completion until `项目规范来源 (Project Rule Sources)` is provided.

### Case 39: Unrelated code change without disclosure (Fail)
Input:
- Diff includes files unrelated to current task, with no disclosure.
Expected:
- Treat as hard failure.
- Block completion and require `Unrelated Change Report` with full fields.

### Case 40: Unrelated code change with full disclosure (Pass With Risk)
Input:
- Unrelated change exists due to build blocker.
- `Unrelated Change Report` includes `Reason`/`Scope`/`Risk`/`Rollback Hint`.
Expected:
- Hard gate passes.
- Risk is explicitly tracked in `风险说明 (Risk Notes)`.

## Java/Kotlin Compatibility Checks

### Java scenario
Input:
- Add Java service method and unit test.
Expected:
- Trigger, enforce hard gates, output fixed sections.

### Kotlin scenario
Input:
- Refactor Kotlin facade method and keep behavior.
Expected:
- Trigger, enforce null-safety validation, output fixed sections.

## V1.6 Lightweight On-Demand Cases

### Case 41: Activated/Skipped rules must both be present (Pass)
Input:
- Any coding request with partial touch scope.
Expected:
- `Rules Applied` includes:
  - `Activated Rules`
  - `Skipped Rules with Reason`
  - Each item uses bilingual format: `id（中文含义）: reason`.

### Case 42: Unactivated hard rule should not block (Pass)
Input:
- L1 task without DB access.
Expected:
- `db_query_bounds` is skipped with reason.
- Missing DB evidence does not block completion.

### Case 43: Activated hard rule missing evidence should block (Fail)
Input:
- Add outbound HTTP call, but no timeout/pool evidence in `Validation`.
Expected:
- Block completion due to activated hard rule evidence gap.

### Case 44: Project rules discovery cache hit (Pass)
Input:
- Second task in same repo/session, rule source files unchanged.
Expected:
- `Project Rule Cache Status` = `hit`.
- Reuse prior discovery result.

### Case 45: Project rules discovery reload on file change (Pass)
Input:
- Rule source file changed after previous run.
Expected:
- `Project Rule Cache Status` = `reload`.
- Re-read source list and refresh conflict resolution.

### Case 46: L1 low-noise checklist output (Pass)
Input:
- L1 task not touching data mutation or batch path.
Expected:
- Keep core checklist rows.
- Conditional rows are omitted or compactly marked with single rationale.

## V1.7 Version Alignment Cases

### Case 47: Framework API change with compatibility evidence (Pass)
Input:
- Modify Spring-related API usage (annotation/config behavior) and provide compatibility evidence against current Java/Spring Boot baseline.
Expected:
- `version_alignment（版本对齐）` is activated.
- `Version Compatibility Check` is `pass` with traceable evidence.

### Case 48: Framework API change without compatibility evidence (Fail)
Input:
- Modify Spring framework usage but provide no baseline-compatible evidence.
Expected:
- `version_alignment（版本对齐）` activated as hard gate.
- Block completion due to missing compatibility evidence.

### Case 49: Pure business logic change (Skipped, Pass)
Input:
- Change only local business logic, no Spring/dependency/config/MyBatis-Spring integration touch.
Expected:
- `version_alignment（版本对齐）` is skipped with low-risk reason.
- No blocking on version-compatibility evidence.

### Case 50: Dependency upgrade without Boot/Java compatibility check (Fail)
Input:
- Request upgrades a starter/library dependency but does not validate compatibility with current Boot/Java baseline.
Expected:
- `version_alignment（版本对齐）` activated as hard gate.
- Block completion and require compatibility proof or fallback decision.

## V1.8 MySQL And ES Alignment Cases

### Case 51: MySQL DDL change with compatibility evidence (Pass)
Input:
- Add/modify table DDL or index and provide MySQL baseline-compatible evidence and fallback decision.
Expected:
- `mysql_version_alignment（MySQL版本对齐）` is activated.
- `MySQL Compatibility Check` is `pass` with traceable evidence.

### Case 52: MySQL dialect feature used without baseline compatibility proof (Fail)
Input:
- Use dialect-sensitive SQL/feature (for example window function/CTE/JSON behavior differences) without proving compatibility with discovered MySQL baseline.
Expected:
- `mysql_version_alignment（MySQL版本对齐）` activated as hard gate.
- Block completion due to missing/incomplete compatibility evidence.

### Case 53: ES real-time scenario declared and implemented consistently (Pass)
Input:
- Touch ES write/read path and declare `Real-time`.
- Provide visibility strategy and latency target evidence.
Expected:
- `es_scenario_alignment（ES场景对齐）` is activated.
- `ES Scenario Check` is `pass`.

### Case 54: ES touched but scenario missing or implementation mismatch (Fail)
Input:
- Touch ES query/index path but do not declare scenario, or declare `Near/Non-real-time` while relying on strict immediate visibility.
Expected:
- `es_scenario_alignment（ES场景对齐）` activated as hard gate.
- Block completion due to missing scenario declaration or scenario-implementation mismatch.

### Case 55: Non-ES/non-MySQL business change (Skipped, Pass)
Input:
- Pure business logic change without MySQL or ES technical surface touch.
Expected:
- `mysql_version_alignment（MySQL版本对齐）` and `es_scenario_alignment（ES场景对齐）` are both skipped with reasons.
- No blocking on MySQL/ES evidence.

## cg-gen Learning Recall Cases

### Case 56: Learning Discovery match with Top-N cap (Pass)
Input:
- Task touches MySQL DDL and batch mutation.
- `docs/rule/codegen-learnings` contains 6 related cards.
Expected:
- `Learning Discovery` is executed.
- Only Top-N (default 3) matched cards are loaded.
- Output includes `Matched Learnings`, `Applied Learnings`, and `Deferred Learnings + reason`.

### Case 56A: Valid five-section card parsed and applied (Pass)
Input:
- Learning card has required five sections:
  - `场景 (Scenario)`
  - `核心约束 (The Golden Rule)`
  - `验证守卫 (Verification Gate)`
  - `风险预警 (Anti-Patterns)`
  - `AI 提示词适配建议`
- And has minimal `machine_block`:
  - `id`
  - `trigger_signals.keywords`
  - `problem_pattern`
  - `recommended_actions`
Expected:
- Card is treated as valid.
- `trigger/problem/actions` can be extracted and mapped.

### Case 56A-1: Trailing-only machine_block is valid (Pass)
Input:
- Five sections are present.
- Only one trailing minimal `machine_block` exists (no frontmatter block).
Expected:
- Card is treated as valid and matched normally.

### Case 56B: Missing five-section required fields (Invalid, Skip)
Input:
- Learning card misses any required section from the five-section contract.
- Or misses minimal `machine_block` required fields.
Expected:
- Card is marked invalid by contract check.
- Card is ignored and not applied.

### Case 56B-1: Missing trailing machine_block (Invalid, Skip)
Input:
- Five sections are present, but no trailing minimal `machine_block`.
Expected:
- Card is marked invalid and ignored.

### Case 57: Matched soft learning deferred (Pass With Risk)
Input:
- A matched card has `severity=soft`.
- Team chooses to defer the recommended action.
Expected:
- Completion allowed.
- Deferral reason appears in `Deferred Learnings`.
- Risk is recorded in `Risk Notes`.

### Case 58: Matched hard learning not adopted and no counter-evidence (Fail)
Input:
- A matched card is marked `severity=hard`.
- Implementation does not adopt the card and provides no counter-evidence.
Expected:
- Block completion.
- Violation is reported under `learning_recall_alignment`.

### Case 59: No matching learning cards (Skipped, Pass)
Input:
- Task is unrelated to any stored learning signals.
Expected:
- `Matched Learnings: none`.
- `learning_recall_alignment` is skipped with reason.

## cg-gen Validation Slim Cases

### Case 60: L1-small outputs only triggered validation items (Pass)
Input:
- L1-small task, no DB/HTTP/MyBatis/learning touch.
Expected:
- `Validation` contains core compile/test/impact items only.
- No DB/HTTP/MyBatis/learning-specific validation sections are emitted.

### Case 61: Learning section appears only when recall is triggered (Pass)
Input:
- Task with no matched learning cards.
Expected:
- `Matched/Applied/Deferred Learnings` fields are not emitted in `Validation`.
