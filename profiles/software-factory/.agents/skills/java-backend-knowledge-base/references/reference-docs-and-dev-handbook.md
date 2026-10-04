# Integrated Reference Docs And Dev Handbook

Use this reference when the user asks to match "参考文档" quality, compares multiple knowledge bases, or points to an existing handbook-style `ai-knowledge-base`.

## Target

The target is one merged `ai-knowledge-base` that works as:

- A business/reference manual.
- A code navigation map.
- A future implementation handbook.

Do not split these into separate alternative outputs. The knowledge base should let an agent answer "what does this business mean?", "where is the code?", and "how should I implement the next change here?" from the same entrypoint.

## Why A Navigation-Only KB Feels Incomplete

A layout optimized only for AI coding navigation can miss content that humans expect from reference docs:

- Full scenario checklists.
- Field-by-field business semantics.
- Exact amount formulas.
- State/review-node meanings.
- Table relationship explanations.
- Flowcharts aligned to historical docs.
- Code-generation conventions and examples.
- Reusable prompt templates.

When these are requested or present in source docs, merge them into the same KB instead of producing only shallow navigation maps and short flow summaries.

## Gap Analysis Workflow

Before editing or generating, compare sources in this order:

1. Existing generated KB.
2. Reference docs, PRDs, flowcharts, Yuque exports, or screenshots.
3. Existing handbook-style KBs in the current repo.
4. Source code evidence from GitNexus and direct file reads.

For each module, record:

| Category | Ask |
|---|---|
| Scenarios | Which business scenarios exist in references but are absent or merged too aggressively? |
| Rules | Which validation lists, branch conditions, and counterexamples are missing? |
| Formulas | Which amount calculations, allocation formulas, and boundaries are missing? |
| Fields | Which request/table/message fields have business meaning not captured by semantic routing? |
| States/Enums | Which entity states, status fields, review nodes, event enums, type enums, MQ tags, or transition rules are missing or under-explained? |
| MQ/Jobs | Which topic/tag/consumer/job contracts are missing? |
| Tables | Which table relationships, status columns, amount columns, idempotency keys, or historical flags need business-semantic explanation? |
| Diagrams | Which final module diagrams are needed for flows, states, dependencies, data lifecycle, and impact surfaces? |
| Handbook | Which code-generation conventions, operation examples, or prompt templates are expected? |
| Review | Which items conflict or require product/dev confirmation? |

## Business/Reference Content

When reference docs exist, required behavior:

- Keep reference scenario names, such as `申请售后`, `售后撤销`, `售后退款`, `售后结转`, `普通下单`, `联报订单`.
- Preserve formulas exactly enough to reimplement or review them.
- Convert image-only flowcharts into Mermaid when possible.
- Add code evidence after business descriptions, not instead of them.
- Add a "文档口径 vs 代码口径" note when code and docs differ.
- Move uncertain or stale statements to `human-review.md`.

Place the content in the integrated layout:

```text
modules/{module}/flow-map.md
modules/{module}/business-rules.md
modules/{module}/state-machine.md
modules/{module}/impact-map.md
modules/{module}/table-structure.md
entity-state-and-enums.md
tags-glossary.md
mq-index.md
diagrams/module-flow-diagrams.md
diagrams/dependency-and-impact-diagrams.md
human-review.md
```

## Implementation Handbook Content

When matching or absorbing a handbook-style KB, preserve equivalent content from files such as:

- `base-knowledge-summary.md`
- `main-table-structure.md`
- `main-tags-glossary.md`
- `code-generate-example.md`
- `mq-operation-example.md`
- `xxl-job-example.md`
- `mapstruct-operation-example.md`
- `prompt-template/*.md`
- `{module}/{module}-knowledge-summary.md`
- `{module}/{module}-main-code.md`
- `{module}/{module}-table-structure.md`
- `{module}/{module}-tags-glossary.md`

Map legacy/handbook content into the integrated canonical layout:

| Legacy/Handbook Content | Canonical Location |
|---|---|
| `base-knowledge-summary.md` | `README.md` + `context.md` |
| `main-table-structure.md` | `context.md` + module `table-structure.md` |
| `main-tags-glossary.md` | top-level `tags-glossary.md` + `context.md` |
| `code-generate-example.md` | `dev-handbook/code-generation-rules.md` |
| `mq-operation-example.md` | `dev-handbook/mq-operation-example.md` |
| `xxl-job-example.md` | `dev-handbook/job-operation-example.md` |
| `mapstruct-operation-example.md` | `dev-handbook/mapstruct-operation-example.md` |
| `prompt-template/*.md` | `dev-handbook/prompt-templates/*.md` |
| `{module}-knowledge-summary.md` | `modules/{module}/README.md` + `flow-map.md` |
| `{module}-main-code.md` | `modules/{module}/README.md` + `flow-map.md` + `agent-guide/task-routing.md` |
| `{module}-table-structure.md` | `modules/{module}/table-structure.md` |
| `{module}-tags-glossary.md` | top-level `tags-glossary.md` unless the vocabulary is truly module-private |

Cross-link handbook files from:

- Top-level `README.md`.
- `agent-guide/task-routing.md`.
- Module `README.md` files when a module has module-specific implementation rules.

## Content Standards

### Business Rules

Good rule entries contain:

- Applicability.
- Preconditions.
- Formula or decision table.
- Counterexample.
- Code evidence.
- Downstream impact.

For complex rules, include a `Source evidence` table that connects each rule to code. A future reader should be able to answer: "Which class/method/enum/table made us document this?"

### Semantic Routing

Good semantic routing entries contain:

- Entrypoint.
- Main service/facade/state/strategy classes.
- Mapper/entity/message classes.
- Read/write side effects.
- "When changing this, also check..." notes.

Put these entries in module `README.md`, module `flow-map.md`, or `agent-guide/task-routing.md`. Avoid standalone `code-map.md` unless the user explicitly requests one and it adds more than package-path listing.

### Entity States And Enums

Good enum/state docs explain:

- Core entity and persisted field, such as `order.state` or `after_sale.state`.
- Enum class and source file path.
- Important enum values and business labels.
- State/event/type enums that drive factories, strategies, MQ tags, validation, formulas, or Mapper queries.
- Allowed transitions and disallowed transitions when visible in code.
- Code evidence for transitions: trigger method, state class, strategy/factory, Mapper write, MQ/external call.

Do not list every constant. Focus on enums that determine behavior or business meaning.

### Table Structure

Good table docs explain:

- Why the table exists.
- Core relationship keys.
- Status and type fields.
- Amount fields and formulas.
- Hidden historical flags.
- Entity/Mapper/XML locations.

They should not copy full DDL by default. Link or name the source directories/files, then explain only the fields and relationships a future agent must understand to change behavior safely.

### Operation Examples

Good examples include:

- File/package placement.
- Minimal implementation steps.
- Constants/config additions.
- Idempotency and retry rules.
- Logging/metrics/alerting expectations.
- Test and review checklist.

### Code And Diagram Information

For AI to understand code better, generate:

- Symbol-level entrypoint maps with exact class/method names.
- Call-chain diagrams for P0/P1 flows.
- State-machine trigger/action/next-state tables.
- Entity state and enum catalogs with stored fields, enum values, transition constraints, and source evidence.
- MQ/job maps with producer, consumer, topic/tag, payload class, idempotency key, retry path.
- Table/entity maps for lifecycle records and write ownership.
- Impact maps listing DB writes, external calls, cache keys, delayed messages, analytics, and compensation jobs.
- Risk/hotspot notes for methods with money calculation, state mutation, async callbacks, or many branches.

For humans to understand code better, generate:

- Business scenario sequence diagrams.
- Module responsibility diagrams.
- Lifecycle diagrams for order, aftersale, payment, refund, shipping, or other domain records.
- Glossary-backed diagrams that show business terms first and code enum/class names second.
- Change checklists attached to common work types.

## Avoid Low-Value Boilerplate

Do not create a file only to satisfy the tree. Skip or defer a file when:

- The module is simple CRUD with no hidden table or generation conventions.
- You would only duplicate obvious Entity fields or existing code.
- There is no source evidence and no useful project convention to record.
- The only possible diagram is a tool-comparison artifact; generate final module diagrams instead.

When unsure, generate a gap list first and mark the missing integrated content as recommended or `待人工确认`.
