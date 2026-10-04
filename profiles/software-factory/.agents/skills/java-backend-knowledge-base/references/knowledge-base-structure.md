# Knowledge Base Structure

## Target Layout

```text
ai-knowledge-base/
├── README.md
├── AI-LOAD-GUIDE.md
├── context.md
├── rules.md
├── entity-state-and-enums.md
├── tags-glossary.md
├── mq-index.md
├── job-index.md
├── impact-map.md
├── human-review.md
├── migration-report.md              # optional, for existing-docs-first updates
├── agent-guide/
│   ├── README.md
│   ├── task-routing.md
│   └── project-facts.md
├── diagrams/                         # optional
│   ├── README.md
│   ├── module-flow-diagrams.md
│   └── dependency-and-impact-diagrams.md
├── dev-handbook/                     # optional
│   ├── README.md
│   ├── code-generation-rules.md
│   ├── mq-operation-example.md
│   ├── job-operation-example.md
│   ├── mapstruct-operation-example.md
│   └── prompt-templates/
└── modules/
    └── {module}/
        ├── README.md
        ├── source-docs-map.md        # optional, for modules merged from existing/reference docs
        ├── flow-map.md
        ├── business-rules.md
        ├── state-machine.md
        ├── diagrams.md
        ├── async-map.md
        ├── impact-map.md
        ├── table-structure.md
        └── human-review.md
```

## Top-Level Files

| File | Purpose |
|---|---|
| `README.md` | Knowledge-base entry, reading order, module index, global indexes. |
| `AI-LOAD-GUIDE.md` | AI on-demand loading protocol; prevents unnecessary full-KB reads. |
| `context.md` | Domain terms, business objects, ID semantics. |
| `rules.md` | Project-level business/engineering hard rules. |
| `entity-state-and-enums.md` | Global state and enum catalog across core lifecycle entities. |
| `tags-glossary.md` | Business vocabulary, aliases, table labels, cross-system names, and search terms. |
| `mq-index.md` | Global MQ production/consumption contracts. |
| `job-index.md` | Global scheduled jobs and compensation tasks. |
| `impact-map.md` | Global cross-system impact map for core lifecycle changes. |
| `human-review.md` | Global questions needing human confirmation. |
| `migration-report.md` | Optional report for existing-docs-first updates: scanned sources, merged content, conflicts, stale items, and deferred work. |

## Agent Guide

`agent-guide/` is not business knowledge. It tells AI agents how to enter the project.

| File | Purpose |
|---|---|
| `agent-guide/README.md` | Startup prompt and minimum reading path. |
| `agent-guide/task-routing.md` | Which files to read for API changes, business-rule changes, SQL changes, MQ changes, debugging, etc. |
| `agent-guide/project-facts.md` | Tech stack, module structure, startup commands, config locations, important dependencies. |

## Module Files

| File | Purpose |
|---|---|
| `README.md` | Module responsibility, core scenarios, reading order, status. |
| `source-docs-map.md` | Optional map from existing/reference docs into module sections, with confirmation status and notes. |
| `flow-map.md` | Core-flow document combining business stages, code path, rules, state changes, DB/MQ/external systems, and evidence. |
| `business-rules.md` | Conditions, formulas, validations, special cases, counterexamples. |
| `state-machine.md` | State, strategy, review, callback, or aggregate lifecycle transitions and state-entry actions. Optional for simple stateless modules; expected for P0/P1 lifecycle modules with any stateful behavior. |
| `diagrams.md` | Module-local Mermaid diagrams: business flow, state lifecycle, async map, data lifecycle, dependency/impact. Expected for P0/P1 modules. |
| `async-map.md` | Module-level MQ, callback, delayed message, job, retry, compensation, and idempotency details. Optional for purely synchronous modules; expected when async exists. |
| `impact-map.md` | Impact map: DB writes, MQ messages, external calls, async jobs. Optional; create for high-risk flows. |
| `table-structure.md` | Business table structure. Optional; create when table relationships, status fields, amount fields, or historical flags encode business meaning. |
| `human-review.md` | Module-specific missing business confirmation. |

## Optional Diagrams

Create top-level `diagrams/` for cross-module understanding. Put detailed flow/state/async/data diagrams in the module's own `diagrams.md`. Do not generate "without tools vs with tools" comparison docs or reference-comparison review assets unless the user explicitly asks for evaluation.

| File | Purpose |
|---|---|
| `diagrams/README.md` | Diagram index and reading order. |
| `diagrams/module-flow-diagrams.md` | Cross-module Mermaid diagrams for important business scenarios and lifecycle paths. |
| `diagrams/dependency-and-impact-diagrams.md` | Cross-module dependency, producer-consumer, table relationship, and impact diagrams. |

## P0/P1 Module Knowledge Pack

For every P0/P1 lifecycle module, generate a complete module knowledge pack unless the project has no evidence for a file. The module should be usable without reading every top-level index first.

Required depth:

- `README.md`: scope, scenarios, reading order, source confidence.
- `flow-map.md`: business stages, code chain, branch table, evidence, state/MQ/DB/RPC notes.
- `business-rules.md`: validations, formulas, edge cases, counterexamples, downstream impact.
- `state-machine.md`: state enum/field/factory/class list, transition table, state-entry actions, source evidence. Include strategy factories, review states, callback status, or aggregate lifecycle states even when there is no formal `StateFactory`.
- `diagrams.md`: module-local flowchart, state diagram, async map, and data/impact diagram when applicable.
- `async-map.md`: producer, consumer, topic/tag, payload, idempotency key, retry/compensation, unknown external consumer.
- `impact-map.md`: DB writes, MQ, RPC, cache/locks, jobs, analytics, failure consequences, regression checks.
- `table-structure.md`: core tables/entities, relationship keys, state/type/amount fields, idempotency and historical flags.
- `human-review.md`: specific unresolved product/dev/domain questions.

Quality note: the skill is generic, but the output is not generic. Write concrete facts for the target project, and mark unsupported reference-doc facts as `待人工确认`.

## Optional Dev Handbook

Create `dev-handbook/` when the target KB should guide future code generation or match an existing handbook-style knowledge base.

| File | Purpose |
|---|---|
| `dev-handbook/README.md` | Handbook index and usage. |
| `dev-handbook/code-generation-rules.md` | Layering, naming, package placement, validation, transaction, and response conventions. |
| `dev-handbook/mq-operation-example.md` | How to add producers/consumers with local base classes, constants, idempotency, retry, and tests. |
| `dev-handbook/job-operation-example.md` | How to add scheduled/XXL jobs with parameters, locking, compensation, and observability. |
| `dev-handbook/mapstruct-operation-example.md` | DTO/entity/API conversion conventions and examples. |
| `dev-handbook/prompt-templates/` | Reusable prompts for common implementation tasks. |

## What Not To Generate By Default

- Do not create `table-structure.md` just to repeat Entity fields or copy DDL. It should summarize business semantics and point to Entity/Mapper/XML/migration directories; include only fields that carry business meaning, formulas, state semantics, idempotency, historical compatibility, or important joins.
- Do not create per-module `mq.md` or `job.md` as duplicate indexes. Use `async-map.md` for module-level async details, and keep `mq-index.md`/`job-index.md` as global indexes.
- Do not create shallow `code-map.md` files that only list package paths. Put semantic routing in module `README.md`, `flow-map.md`, or `agent-guide/task-routing.md`.
- Do not create `business-flows.md` and `code-flow-map.md` by default. Use `flow-map.md` to keep business stage, code path, and evidence together.
- Do not create giant glossary files for every enum if the enum is easy to locate in code; use top-level `tags-glossary.md` for business vocabulary, aliases, table labels, and cross-system vocabulary.
- Do not dump every enum. Use top-level `entity-state-and-enums.md` for enums that affect behavior, persistence, routing, state transition, money calculation, MQ/job contracts, or cross-system meaning.
- Do not generate tool-evaluation folders unless the task explicitly evaluates GitNexus/Graphify or other tooling.
