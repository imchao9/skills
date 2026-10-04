# Knowledge Base Quality Checklist

Use this checklist before finishing a generated or updated `ai-knowledge-base`.

## Global Checks

- [ ] Existing knowledge sources were checked before generation (`ai-knowledge-base/`, `docs/`, `doc/`, `knowledge-base/`, `wiki/`, architecture/design docs, root README/agent docs, and user-provided reference docs).
- [ ] If existing docs were found, useful human-authored content was preserved or cross-linked, not overwritten wholesale.
- [ ] If existing docs were found and the update was non-trivial, `migration-report.md` or a final migration summary records merged, stale, conflicting, and deferred items.
- [ ] `README.md` is a navigation map, not a long manual.
- [ ] `AI-LOAD-GUIDE.md` exists or the KB has an equivalent on-demand loading protocol.
- [ ] `context.md` explains domain objects, IDs, ownership boundaries, and external systems.
- [ ] `rules.md` contains hard rules, formulas, state constraints, idempotency boundaries, and cross-system invariants.
- [ ] `entity-state-and-enums.md` is a global state/enum index with enum class, stored field, value, use site, and evidence.
- [ ] `mq-index.md` lists producer, consumer, topic/tag, payload, idempotency, and downstream owner or `待人工确认`.
- [ ] `job-index.md` lists handler, params, scan scope, writes, side effects, idempotency, and failure behavior.
- [ ] `tags-glossary.md` explains business vocabulary and search aliases, not just MQ constants.
- [ ] `impact-map.md` gives cross-module impact, not a vague side-effect list.
- [ ] `human-review.md` contains specific answerable questions.

## P0/P1 Module Pack Checks

For every P0/P1 lifecycle module:

- [ ] Module has a clear scenario scope and reading order in `README.md`.
- [ ] Module docs are concrete to the current project; they are not generic placeholders.
- [ ] `flow-map.md` includes trigger, preconditions, main stages, branch table, code chain, side effects, and evidence.
- [ ] `flow-map.md` includes a code-chain Mermaid diagram with concrete class/method names. A business-only diagram is not enough.
- [ ] `business-rules.md` includes validations, formulas, edge cases, counterexamples, and downstream impact.
- [ ] `state-machine.md` exists when there are explicit states, review states, strategy factories, callback states, aggregate states, or job-repaired states.
- [ ] `state-machine.md` includes stored field/entity, enum/factory/strategy, state class list, transition table, state-entry actions, and Mermaid diagram.
- [ ] `diagrams.md` exists for P0/P1 modules unless the module is too trivial.
- [ ] Module diagrams include at least the most useful two of: business flow, code-chain swimlane or sequence diagram, state lifecycle, async map, data lifecycle, impact map.
- [ ] Stateful modules include a `stateDiagram-v2`; table-heavy modules include a data lifecycle `flowchart` or `erDiagram`.
- [ ] Every P0/P1 module includes a business `flowchart` and a code-flow swimlane `flowchart` with concrete class/method names.
- [ ] Request/callback/external interaction flows include a `sequenceDiagram` when call order matters.
- [ ] Modules with MQ/job/callback/retry include an async diagram and async table.
- [ ] High-risk money/state/external-impact modules include an impact diagram.
- [ ] Complex P0/P1 modules include scenario-specific diagrams for major variants instead of only one generic graph.
- [ ] Complex P0/P1 modules include a validation/eligibility decision tree when there are multiple reject/allow branches.
- [ ] Formula-heavy modules include a calculation diagram showing inputs, branch modes, formulas, and final persisted fields.
- [ ] Stateful/review/callback-heavy modules include a state swimlane diagram grouped by persisted state or review node, not only a compact state diagram.
- [ ] System/deployment dependency diagrams are generated only when config/docs support them; otherwise missing infrastructure facts are marked `待人工确认`.
- [ ] `async-map.md` exists when the module has MQ, callback, delayed message, job, retry, or compensation.
- [ ] `async-map.md` includes both producers and consumers; unknown external consumers are marked `待人工确认`.
- [ ] `impact-map.md` is a matrix with DB/MQ/RPC/cache-or-lock/job/failure/regression columns when applicable.
- [ ] `table-structure.md` explains table/entity responsibilities, relationship keys, status/type/amount/idempotency fields, and source locations.
- [ ] Module `human-review.md` lists unresolved questions specific to that module.

## Evidence Checks

- [ ] Existing-doc claims are labeled or treated according to confidence: code-confirmed, `待人工确认`, `疑似过期`, or historical context.
- [ ] Important claims cite class/method/file, endpoint path, enum value, topic/tag, entity/mapper, or job handler.
- [ ] GitNexus output is treated as candidate evidence and important claims are confirmed against source files.
- [ ] Each P0/P1 flow has at least one GitNexus `query` recorded in working notes or final summary, plus source confirmation for the selected symbols. If GitNexus cannot resolve context, the fallback is explained.
- [ ] Reference-doc facts are copied only when supported by current project code/docs.
- [ ] Unsupported but useful reference-doc facts are marked `待人工确认`.
- [ ] Code facts and business wording are not mixed without explanation.

## Density Checks

- [ ] P0/P1 module docs are not one-page summaries.
- [ ] State docs do more than list enum names.
- [ ] Flow docs do more than list Controller -> Service.
- [ ] Code-flow diagrams do more than list generic layers; they name the actual project classes/methods and show DB/MQ/external edges.
- [ ] Business rules do more than restate method names.
- [ ] Impact maps include failure consequences and regression checks.
- [ ] Table docs include business semantics, not full DDL dumps.
- [ ] Async docs include idempotency and retry/compensation behavior.

## Domain-Neutral Skill Checks

- [ ] The skill itself does not bake in project-specific business facts.
- [ ] Domain examples are clearly labeled as shape/quality examples.
- [ ] Generated output is project-specific and deep for the current project.
- [ ] If the target project is not an order system, no order-specific default flows are forced into the KB.

## Finish Summary Checks

The final response should report:

- [ ] Files created/updated.
- [ ] Modules covered.
- [ ] P0/P1 flows documented.
- [ ] Reference docs consulted and how they were used.
- [ ] GitNexus commands used, if any.
- [ ] Items marked `待人工确认`.
- [ ] Known gaps and recommended human review.

## Hard Failure Conditions

Do not present the KB as complete when any of these are true for a selected P0/P1 module:

- The module only has a file tree or short summaries.
- The main flow lacks a concrete class/method code-chain diagram.
- Complex scenario variants are collapsed into one generic flow with no variant diagrams.
- A formula-heavy flow has no calculation diagram.
- A validation-heavy flow has no decision tree.
- A stateful/review-heavy flow has no state swimlane or transition table.
- A stateful flow lacks a transition table or state diagram.
- Table docs only list table/entity names without relationship keys or business fields.
- Async docs omit idempotency/failure/compensation for flows that use MQ, jobs, callbacks, or retries.
- Important business rules have no source evidence and are not marked `待人工确认`.
