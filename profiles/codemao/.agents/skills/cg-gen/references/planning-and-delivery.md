# cg-gen Planning And Delivery

Load this reference for `Plan-Lite`, `Plan-Full`, plan persistence, plan-to-code mapping, and post-code delivery decisions.

## Plan Stage
Before execution in `Implement Mode`, select one plan state:
- `Plan-Skipped`: tiny scoped change or user explicitly requests direct implementation.
- `Plan-Lite`: compact 3-6 line plan with `改动点/风险点/验证点`.
- `Plan-Full`: full plan for high-risk or cross-module changes.

Recommendation signals for upgrading from `Plan-Skipped`:
- Trigger Profile is `L2-Standard` or `L3-HighRisk`.
- External HTTP call is added or modified.
- DB write path is added or modified.
- Cross-module changes are required.

The recommendation is non-blocking. If the user continues with `Plan-Skipped`, record skip reason and residual risk in `Risk Notes`.

## Plan-To-Code Mapping
In `Implement Mode`, provide or maintain:

| 方案条目 | 代码位置 | 验证项 | 状态 |
| --- | --- | --- | --- |
| <plan item> | <file/module/method> | <verification> | `pending/done/partial/deferred/N-A(with reason)` |

Gate rules:
- `Plan-Lite` and `Plan-Full`: incomplete required mapping is a hard failure.
- `Plan-Skipped`: mapping may be `N-A(with reason)`, but the reason and residual risk must be tracked.

## Plan-Full Persistence
When entering `Plan-Full`, first show the full plan in conversation, then ask for persistence choice:
- `Display-Only（仅展示，不落库）`
- `Display-And-Persist（展示并落库文档）`

Reuse the user's explicit choice if already provided in the same request.
Map colloquial `落库` or `存档` to `Display-And-Persist`.
If no choice is available after the plan is shown, pause and wait for user selection.

Persistence path:
- Directory: `docs/plans/`
- Filename: `{topic}-{yyyyMMdd-HHmm}-plan.md`
- Topic: prefer requirement topic keywords; fallback to `general-plan`.

Validation result format:
- `display-only`
- `persisted -> docs/plans/<topic>-<yyyyMMdd-HHmm>-plan.md`
- `persist-failed -> docs/plans/<topic>-<yyyyMMdd-HHmm>-plan.md -> <reason>`

## Post-Code Delivery Decision
Run this only in `Implement Mode` after code changes and required validation/checklist are complete.

Goal:
- Let the user decide whether the implementation summary should be persisted to documentation.
- Let the user decide whether test points should be generated.
- Avoid forcing documentation or test-point generation when the user wants the task to end.

Required behavior:
1. After successful validation, use compact completion output by default.
2. If project delivery/checklist items were found, output conforming and non-conforming items.
3. If any non-conforming item exists, ask whether to fix before documentation/test-point decisions:
   - `是，修正不符合项`
   - `否，结束当前任务`
4. If the user answers no, end the task after reporting non-conforming items.
5. If the user answers yes, fix only non-conforming items, rerun relevant validation, and repeat checklist fit summary.
6. Then ask one numbered-choice question and wait before extra documentation/test-point work:
   1. `不落文档，不生成测试要点，结束任务`
   2. `只生成测试要点`
   3. `只把改动点落到文档`
   4. `改动点落到文档，并生成测试要点`

Free-form equivalents:
- `不要/不用/结束` -> choice 1
- `测试要点` -> choice 2
- `落文档/存档/改动点文档` -> choice 3
- `都要/都生成` -> choice 4

Documentation behavior:
- Default directory: `docs/features/`
- Filename: `{topic}_改动点.md`
- If a related requirement or technical-plan document exists, prefer appending a short `实施改动点` section there instead of creating a duplicate document.
- Record write path and status in the final response.

Test-point behavior:
- Generate concise `测试要点` grouped by functional path, abnormal path, regression path, and observability when relevant.
- If documentation is also selected, include test points in the persisted document.
- If documentation is not selected, return test points inline only.

This interaction must not mask failed hard validation and is skipped in `Review-Only Mode` or when no code changed.
