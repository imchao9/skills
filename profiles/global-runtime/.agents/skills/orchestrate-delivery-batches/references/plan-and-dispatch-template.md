# Plan and dispatch template

Use this template when the work spans several tickets or fresh contexts. Remove headings that genuinely do not apply.

```markdown
# <Feature> delivery plan

## Objective
<User-visible outcome>

## Scope
- In: ...
- Out: ...

## Done contract
| Level | Required evidence |
|---|---|
| Code complete | ... |
| Automated verification | ... |
| Deployment | ... |
| Upstream readback | ... |
| Human /现场验收 | ... |

## Current evidence and assumptions
- Fact: ...
- Assumption: ...
- Unknown: ...

## Core vertical chains
1. <Actor → action → system boundary → observable result>
2. ...

## Ticket graph
| Ticket | Vertical outcome | Blocked by | Acceptance | External gate |
|---|---|---|---|---|
| T1 | ... | None | ... | ... |

## Batch and model routing
| Batch | Ticket | Owner / role | Model tier | Why | Owned area | Batch gate |
|---|---|---|---|---|---|---|
| 1 | T1 | worker | balanced | bounded slice | ... | ... |

## Verification and release
- Ticket checks: ...
- Integration checks: ...
- Independent review: ...
- Release authority required: ...
- Rollback or fail-closed boundary: ...

## Progress ledger
| Ticket | Status | Evidence | Remaining blocker |
|---|---|---|---|
| T1 | pending | — | — |
```

## Dispatch brief

Every agent brief should contain:

```markdown
Ticket: <ID and outcome>
Plan: <absolute or repository-relative plan path>
Blocked by: <completed prerequisites>
Ownership: <files/modules/responsibility>
Contract: <inputs, outputs, state transitions, failure behavior>
Acceptance: <commands and observable result>
Boundary: <no commit/deploy/production writes unless explicitly authorized>
Coordination: You are not alone in the codebase. Preserve unrelated edits and do not revert other agents.
Return: changed files, tests run, failures, remaining human/external verification.
```

The ticket remains outcome-oriented; file ownership belongs in the temporary dispatch brief because it may change as the codebase changes.
