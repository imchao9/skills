# Layout Bank

Use varied page forms. A technical deck should not be a sequence of identical title-and-cards pages.

## Core Layouts

`decision-cover`
: Meeting title, decision ask, scope, date/version, and one strong system visual.

`executive-verdict`
: One sentence recommendation, three supporting reasons, explicit decision needed.

`objection-ledger`
: Objection, real concern, mitigation, residual risk. Use for cost/benefit resistance.

`architecture-map`
: Layers, boundaries, ownership, data direction, failure isolation.

`sequence-flow`
: Actor to system to storage/event path. Show query/report separation when relevant.

`state-or-rule-model`
: State machine, rule priority, event schema, or evaluation order.

`before-after`
: Old path versus new path, with cost, coupling, observability, and rollback impact.

`risk-register`
: Risk, trigger, signal, mitigation, owner, decision gate.

`rollout-roadmap`
: Phases, migration boundary, validation signal, rollback point.

`acceptance-gates`
: Test scenarios, metrics, observability, audit evidence, launch gates.

`appendix-dense`
: Dense but readable reference page for source tables, endpoint lists, or rule matrices.

## Rhythm Rule

For 8-12 page technical decks, include at least:

- one verdict page
- one architecture page
- one flow or model page
- one objection or tradeoff page
- one rollout page
- one acceptance gate page

Avoid more than two consecutive card-grid pages.

## Text Density

Use short visible text on decision pages. Use denser text only for appendix or reference slides.

For Chinese slides, keep labels concrete:

- prefer `登录失败上报` over `能力沉淀`
- prefer `query/report 分离` over `架构优化`
- prefer `Redis 计数 + TTL` over `高性能存储`
