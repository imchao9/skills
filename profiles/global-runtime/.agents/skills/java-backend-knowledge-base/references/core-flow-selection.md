# Core Flow Selection

Do not document all endpoints equally. Prioritize flows that are complex or risky for AI coding.

## Priority Rules

Start from domain lifecycle discovery, not from a fixed list of modules. A core flow is usually a business verb that moves a primary record through states, money, allocation, fulfillment, approval, callback, or compensation.

## Lifecycle Archetypes

Use these generic archetypes to identify project-specific P0/P1 flows:

| Archetype | Code/doc signals | What to document |
|---|---|---|
| Creation / intake | `create`, `submit`, `place`, `apply`, `open`, `init`, `import`, POST endpoints, insert into primary tables | Preconditions, identity generation, validation, initial state, core writes, downstream events. |
| Pricing / calculation / allocation | `calculate`, `price`, `discount`, `amount`, `quota`, `score`, `allocate`, strategy factories, formula-heavy code | Inputs, formulas, rounding, boundaries, type branches, persistence fields, caller flows. |
| Approval / review / decision | `review`, `approve`, `audit`, `check`, state transition strategies, review enums | Review roles, allowed states, approve/reject next states, logs, notifications. |
| Payment / settlement / financial callback | `pay`, `settle`, `refund`, `reconcile`, `transfer`, payment clients, financial MQ | Full/partial/failed states, idempotency, amount boundaries, downstream messages, compensation. |
| Fulfillment / delivery / provisioning | `ship`, `deliver`, `fulfill`, `provision`, `activate`, logistics/inventory clients, callback consumers | Trigger rules, external systems, callback states, partial success, cancellation/stop rules. |
| Change / cancellation / reversal | `cancel`, `close`, `revoke`, `rollback`, `return`, `exchange`, `disable`, `void` | Eligibility, state rollback, financial reversal, resource release, side effects. |
| Async compensation / repair | `retry`, `repair`, `compensate`, `job`, `stuck`, `timeout`, delayed messages | Scan scope, idempotency boundary, retry state, failure handling, alerting. |

For order-management domains, these archetypes often surface as: 下单, 优惠金额计算, 支付, 售后, 发货. Treat them as domain-specific outcomes of the archetype scan, not as universal defaults.

| Priority | Signal | Examples |
|---|---|---|
| P0 | State machine | Review, approval, payment completion, fulfillment, return/reversal, lifecycle completion. |
| P0 | Complex calculation | Price, discount, refund, settlement, quota, score, allocation, entitlement. |
| P0 | Multi-system impact | MQ, payment, logistics, promotion, CRM, analytics, account, inventory, workflow. |
| P1 | Many branches | Type-specific flows, one-to-many relationships, channel/platform branches, special compatibility. |
| P1 | Async callback or compensation | MQ consumer, scheduled job, retry, timeout, stuck-state repair, import compensation. |
| P1 | Historical compatibility | Account switching, associated records, legacy statuses, before/after migration compatibility. |
| P2 | CRUD or query-only | Keep as a short README/task-routing note; do not expand into detailed flow docs unless requested. |

## Candidate Discovery Checklist

Look for:

- External HTTP/RPC entrypoints.
- MQ consumers and producers.
- Job handlers.
- State factories and state classes.
- Core entity state fields and important enums.
- Strategy factories.
- Methods that write core tables.
- Methods that call external clients.
- Amount calculation classes or methods.
- Methods with many branches or type-specific logic.

## Scoring Heuristic

Give one point for each:

- Writes core business tables.
- Triggers MQ or delayed message.
- Calls external systems.
- Uses a state machine.
- Mutates or depends on core entity state fields.
- Routes behavior through important enums, state classes, strategy factories, or event constants.
- Calculates money, score, quota, entitlement, allocation, refund, settlement, risk, or other business formulas.
- Has async callback or compensation.
- Has 3+ business branches.
- Appears in reference docs, requirements, incidents, or team concerns.

Suggested actions:

- `score >= 5`: generate or update `flow-map.md`, `business-rules.md`, and `impact-map.md`; add `state-machine.md` when applicable and update top-level `entity-state-and-enums.md`.
- `score 3-4`: generate a focused `flow-map.md` section; update rules or impact map when the flow has durable business meaning.
- `score <= 2`: keep as a short module README or task-routing note; avoid creating shallow code-map entries.

## Traceability Requirement

For any selected P0/P1 flow, do not write business-only prose. Pair the document with code evidence:

- Reference-doc scenario or business step.
- Entrypoint method or consumer/job handler.
- Core service/facade method.
- State enum/value and state class when applicable.
- Strategy/factory class when applicable.
- Mapper/entity/table fields written.
- MQ topic/tag or external client when applicable.
- Human-review note when the reference doc and code cannot be reconciled.

## Human Confirmation

Ask humans about:

- Which candidate flows are truly business-critical.
- Product/operations rules not visible in code.
- Historical pitfalls and incident-prone areas.
- Whether a state transition is intentional or legacy.
- Which formulas are official business definitions.
