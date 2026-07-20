# Gate Rubric

Use this rubric to classify a business feature technical plan as `通过`, `有条件通过`, or `不通过`.

Internal English mappings are `通过=pass`, `有条件通过=conditional pass`, and `不通过=fail`.

The reviewed artifact is the technical plan by default. Requirement evidence is used to judge business alignment; it is not the primary artifact unless the user explicitly asks for requirement review.

Reviews can happen in two stages:

- `编码前方案准入`: decide whether implementation can start responsibly.
- `编码后实现核验`: decide whether existing code matches the plan well enough to proceed to test, merge, or release.

## Dimensions

### Requirement Context

Pass when the review has enough requirement context to judge the plan against the intended business outcome. Acceptable evidence includes fetched DingTalk requirement docs, accessible referenced requirement files, embedded requirement content in the plan, or explicit requirement context supplied by the user in the current conversation.

Fail when no requirement context is available and the plan only describes implementation mechanics without business goal, actor, scope, business rules, acceptance intent, and exclusions. A missing external requirement document is not a failure by itself when the technical plan embeds enough business context.

Conditional pass when the main intent is clear, but small acceptance details, wording, or low-risk scope edges need confirmation.

### Requirement Alignment

Pass when the plan makes the business goal, primary user or actor, scenario, scope boundary, and acceptance intent clear enough to judge whether the technical design supports the requested feature.

Fail when the plan omits or contradicts the core business behavior, leaves the primary scenario ambiguous, or makes implementation choices that cannot be evaluated against a clear outcome.

Conditional pass when the business intent is clear but minor acceptance details can be clarified during development.

### Implementation Readiness

Pass when the plan identifies the main flows, data behavior, interface behavior, state transitions, dependencies, error handling, and affected components at a level that supports task breakdown.

Fail when a developer or agent would have to invent core behavior, guess affected modules, infer data ownership, design missing exception paths, or decide critical integration contracts during implementation.

Conditional pass when unresolved details are local, low-risk, and do not change task boundaries or core design.

### Code-State Consistency

Pass when implementation-relevant claims about existing code are confirmed, or when proposed new work is clearly described as target state.

Fail when the plan depends on existing modules, APIs, tables, permissions, jobs, configuration, or flows that do not exist or behave differently, and the plan does not acknowledge the required change.

Fail when the target repository cannot be located or confirmed and the missing repository evidence affects core design, integration points, data behavior, permissions, migrations, rollback, or tests.

Conditional pass when the mismatch is real but the plan names it as a required change and the missing migration or adaptation detail is small enough to resolve before or during early implementation.

Conditional pass when repository inspection is partial or a material code claim is unverified, but the unchecked claim is bounded and does not affect core architecture, data model, integration contract, or task breakdown.

### Plan-Implementation Consistency

Use this dimension only for `编码后实现核验`; otherwise mark it `不适用`.

Pass when implemented code, tests, config, migrations, and interface behavior match the plan's target behavior, non-goals, risk controls, and rollback expectations.

Fail when the implementation omits a core planned behavior, implements behavior outside the plan's scope, changes a protected existing behavior, or contradicts a planned data, permission, interface, migration, or rollback decision.

Conditional pass when the mismatch is narrow, low-risk, and can be fixed without changing the plan, architecture, data model, integration contract, or task breakdown.

### Risk Control

Pass when relevant risks are addressed: data consistency, compatibility, permissions, security, performance, idempotency, retries, rollout, rollback, compensation, observability, and user-visible failure modes.

Fail when an unhandled risk can corrupt data, expose unauthorized behavior, break existing workflows, strand user state, cause irreversible migration damage, or make rollback unclear for a risky change.

Conditional pass when risks are identified and bounded, but minor mitigation details still need confirmation.

### Test Sufficiency

Pass when the test plan covers core behavior, integration points, regression paths, permission boundaries, data consistency, and important failure cases.

Fail when tests only cover happy paths while the plan changes critical data, permissions, external interfaces, workflows, or compatibility behavior.

Conditional pass when missing tests are narrow and can be added without changing the implementation approach.

## Blocking Finding Triggers

Mark an issue as blocking when any of these are true:

- The plan has no accessible DingTalk requirement, referenced requirement material, embedded requirement context, or user-provided requirement context, and therefore cannot be judged against a clear business outcome.
- A DingTalk requirement link is present but cannot be fetched, no equivalent requirement context is embedded in the plan, and the missing context affects business alignment. If DingTalk MCP is unavailable, the finding must tell the user to either connect DingTalk MCP from `https://aihub.dingtalk.com/#/detail?instanceId=600280&detailType=instanceMcpDetail&mcpId=9629` or paste the requirement body.
- The requirement source and technical plan conflict on scope, acceptance, actor, data behavior, permission behavior, or delivery boundary.
- The plan does not identify the code area that must change, and the repository does not make the target obvious.
- The plan relies on an existing capability that repository evidence refutes.
- The target repository cannot be located or confirmed, and this prevents verification of core implementation claims.
- A material code-state claim is unverified and affects the implementation approach, data correctness, permissions, external interfaces, migration, rollback, critical tests, or plan-implementation consistency.
- In `编码后实现核验`, the stage is inferred only from historical code existence without user statement, PR/MR, diff, or changed-file evidence.
- In `编码后实现核验`, implemented code materially diverges from the plan's target behavior, non-goals, interface contract, data behavior, permission behavior, rollback path, or risk controls.
- In `编码后实现核验`, planned tests or equivalent verification are missing for the main changed behavior or risk.
- The core business flow has unresolved branches that affect implementation.
- Data ownership, lifecycle, consistency, or migration behavior is unclear for changed state.
- Interface contracts are too vague to implement or test.
- Permission, security, or tenancy behavior is missing where relevant.
- Failure handling, retry, compensation, or rollback is missing for a risky path.
- The test plan misses the main risk introduced by the change.

## Conditional Finding Triggers

Use `有条件通过` when gaps are real but bounded:

- Requirement wording or a low-risk acceptance edge needs confirmation, but the requirement context and core scope are clear.
- A named field, copy detail, or enum value needs final confirmation.
- A small test addition is needed for a clearly understood behavior.
- DingTalk fetching failed but the plan embeds enough equivalent requirement context; record `钉钉原文未验证` and only make it conditional when original-document verification matters.
- Repository inspection is partial, but the unchecked areas are bounded and do not affect core implementation readiness.
- In `编码后实现核验`, a small implementation or test mismatch exists but is narrow, low-risk, and does not alter the plan's core design.
- A low-risk implementation detail can be decided by following an existing local pattern.
- A non-critical dependency version or configuration detail needs confirmation.

Do not use `有条件通过` for uncertainty that can change the architecture, data model, integration contract, or task breakdown.

## Evidence Discipline

For each material claim, classify evidence as:

- `confirmed`: verified with repo-relative `file:line` evidence.
- `refuted`: contradicted by repo-relative `file:line` evidence.
- `unverified assumption`: not confirmed after targeted search.
- `not checked`: only acceptable for non-material claims; avoid in final blockers.

Prefer direct source files over generated docs. Use documentation only when it is the authoritative source for the project.

## Required Questions

Each blocking or conditional finding should produce a question that the plan author can answer. Good questions are specific and action-forcing:

- "Which existing state transition should this hook into, or is this plan introducing a new transition?"
- "What is the expected behavior when the downstream write succeeds but the audit write fails?"
- "Is this API new target-state work, or did the plan assume it already exists?"
- "Which regression cases prove existing users keep the old behavior?"

Avoid vague questions such as "Can you clarify this?" or "What about tests?"
