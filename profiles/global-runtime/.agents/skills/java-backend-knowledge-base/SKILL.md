---
name: java-backend-knowledge-base
description: Generate or update an AI-friendly knowledge base for Java/Kotlin backend projects. Use when creating ai-knowledge-base docs, identifying complex core flows, using GitNexus to map code paths, producing code-flow/state-machine/impact maps, or converting reference docs and backend code into maintainable project knowledge.
---

# Java Backend Knowledge Base

Build an AI-friendly knowledge base for Java/Kotlin backend projects. Optimize for future AI coding,方案设计,排障, and human review.

## Core Principles

- Do not document every API equally. Prioritize flows that are complex, risky, stateful, asynchronous, or money-related.
- A generated P0/P1 module pack is not complete until it passes the P0/P1 quality gate: concrete code-chain diagram, state/transition diagram when stateful, DB/MQ/external impact matrix, table business semantics, and source evidence for important claims. Creating the target directory tree is not enough.
- Prefer business-core lifecycle documentation over module-directory documentation. Identify the domain's primary lifecycle verbs from code and docs, then document those lifecycle flows deeply. Treat cross-system integrations as impact surfaces unless an integration is itself a primary lifecycle.
- Keep the skill generic, but make each generated knowledge base project-specific. Do not bake order, account, payment, CRM, or other domain facts into the skill as defaults. When applying the skill to a concrete project, deeply mine that project's code, docs, reference material, enums, tables, MQ, jobs, and terminology, then write the concrete business facts that are useful for that project.
- Reference docs are quality and structure signals, not reusable business truth. Absorb reusable patterns such as state tables, formula sections, MQ contracts, table semantics, scenario checklists, and diagram styles. Only copy domain facts into the target KB when the current project code/docs support them; otherwise mark `待人工确认`.
- Do not dump entity/table fields. Point agents to Entity/Mapper/migration locations unless the schema carries hidden business meaning.
- Separate business knowledge from agent operating instructions.
- Mark uncertain business meaning as `待人工确认`; do not invent rules.
- Use GitNexus as the default code-structure tool. Use Graphify only when external docs, PRDs, audio transcripts, historical plans, or cross-project knowledge need to be linked with code.

## Completion Gate For P0/P1 Modules

Before reporting completion, every selected P0/P1 lifecycle module must satisfy these hard checks. If any check fails, continue improving the module or explicitly report it as incomplete/draft:

- `flow-map.md` contains a business-stage table and a code-chain diagram with concrete class/method names from entrypoint to facade/service/strategy/state/mapper/MQ/client.
- `diagrams.md` contains the required module-local Mermaid diagrams for the flow type. For P0/P1 modules, default required diagrams are: business flowchart, code-flow swimlane, call sequence diagram, state lifecycle diagram when stateful, data/table relationship diagram when tables carry business meaning, async diagram when MQ/job/callback exists, and impact diagram for high-risk flows.
- When reference-style flow docs are expected or examples are provided, add richer business-understanding diagrams: scenario-specific diagrams, validation/eligibility decision trees, formula/calculation diagrams, state-swimlane diagrams, and scenario-variant diagrams. A generic all-in-one flow is not enough for complex P0 flows.
- System/deployment dependency diagrams are optional, not a P0 module hard gate. Generate them when configuration files such as `application.yml`, `application.yaml`, `bootstrap.yml`, or environment docs reliably identify DB/Redis/MQ/external dependencies; otherwise record the gap instead of guessing.
- `business-rules.md` contains validations, formulas/boundaries, edge cases, and downstream impact, each with code evidence.
- `state-machine.md` exists when the flow has enum states, review states, strategy factories, callback states, aggregate states, or job-repaired states, even if there is no formal state-machine class.
- `async-map.md` exists when there is MQ, callback, delayed message, job, retry, or compensation, and includes producer/consumer, topic/tag or handler, payload/params, idempotency, failure/compensation, and evidence.
- `impact-map.md` is a matrix with DB writes, MQ, RPC/external clients, cache/locks, jobs/delays, failure consequences, and regression checks where applicable.
- `table-structure.md` explains table responsibilities, relationship keys, status/type/amount/idempotency/historical fields, and Entity/Mapper/XML/migration locations. A table list alone is not sufficient.
- Important claims cite class/method/file path, endpoint path, enum value, topic/tag, entity/mapper, migration, or job handler.

If the initial pass only creates a skeleton, call it a skeleton and continue with a depth pass instead of presenting it as regenerated knowledge.

## Default Intent

When the user asks to generate or update `ai-knowledge-base`, treat the implicit request as:

> Generate or incrementally update an integrated Java backend knowledge base for the current project. Combine source code, existing project docs, provided reference docs, and any existing `ai-knowledge-base`. Preserve fine-grained business rules, formulas, code navigation, table business semantics, tag glossary, implementation handbook content, and module-level Mermaid diagrams. Do not generate tool-comparison documents unless explicitly requested.

The user should not need to restate quality constraints. A short request such as "use this skill to generate ai-knowledge-base" must still mean:

- Use the latest skill behavior and references.
- Keep the skill domain-neutral, but make the generated KB concrete and deep for the current project.
- Use provided reference docs as structure/quality examples, not as default business facts.
- Identify P0/P1 flows from the current project and generate complete module knowledge packs for them.
- Keep global files as indexes and cross-module summaries; do not let them replace module-level depth.
- Mark unsupported business meaning as `待人工确认`.
- Run a lightweight validation pass, including Markdown link checks when practical, and report coverage and gaps.

Default deliverables:

- Fine-grained business rules from reference docs and code, including validation lists, branch conditions, formulas, boundaries, states, MQ/job contracts, and cross-system side effects.
- Core-flow docs that merge business stages with implementation paths. Prefer `flow-map.md` over separate `business-flows.md` and `code-flow-map.md` unless the user explicitly wants separated views.
- A complete module knowledge pack for each P0/P1 flow. A module should be readable on its own: scenario scope, code entrypoints, state/strategy transitions, formulas, table semantics, async map, diagrams, impact matrix, and change checklist. Top-level files are indexes; they must not replace module-level depth.
- Code navigation only where it adds semantic routing value. Do not create shallow `code-map.md` files that merely list Controller/Service/Mapper paths.
- Source traceability for complex flows: each important business stage, state transition, formula, and side effect should point back to the code class/method/file that supports it.
- A top-level `entity-state-and-enums.md` that unifies important lifecycle states, domain type enums, review/event enums, amount/discount type enums, MQ/job routing constants, and persisted status fields across modules. Module docs may link to it instead of duplicating enum catalogs.
- `table-structure.md` files that explain key table business semantics and source locations, without copying full DDL or every field.
- `tags-glossary.md` for business vocabulary and aliases that help AI understand requirements and search code. It should explain domain terms, lifecycle names, synonyms, table labels, cross-system names, and confusing words; it should not be just an MQ tag list.
- `dev-handbook/` with code-generation rules, MQ/job/MapStruct operation examples, and reusable prompt templates when local conventions can be inferred.
- Final module diagrams such as module flow diagrams, state lifecycle diagrams, producer-consumer maps, data lifecycle diagrams, dependency diagrams, and impact maps.

Default exclusions:

- Do not generate `tool-evaluation/`, "without tools vs with tools", or reference-comparison review files unless the user explicitly asks to evaluate tooling or compare approaches.
- Do not replace useful existing KB content wholesale; update conservatively and cross-link new material.

## When Starting

1. First determine whether an existing knowledge base or project documentation already exists. Check `ai-knowledge-base/`, `docs/`, `doc/`, `knowledge-base/`, `knowledge/`, `wiki/`, `architecture/`, `design/`, root README/agent docs, and user-provided reference docs.
2. If a knowledge base exists, use existing-docs-first update mode: inventory it, preserve useful human-authored content, validate with code, merge confirmed facts, and mark stale/conflicting facts instead of overwriting.
3. Inspect code layout and project facts.
4. If GitNexus is available, index the target project before identifying core flows.
5. If no external docs are provided, use GitNexus only after existing knowledge has been checked.
6. If external docs are provided, use GitNexus for code facts and Graphify or manual doc reading for cross-document business semantics.
7. If the user's prompt is short, do not ask them to repeat default constraints from this skill. Apply the defaults and proceed. Ask only when the target project, write location, or destructive overwrite behavior is genuinely ambiguous.

Read these references only as needed:

- [knowledge-base-structure.md](references/knowledge-base-structure.md): target file structure and file responsibilities.
- [gitnexus-workflow.md](references/gitnexus-workflow.md): GitNexus commands, query patterns, and how to turn results into docs.
- [core-flow-selection.md](references/core-flow-selection.md): rules for selecting P0/P1 core flows.
- [document-guidelines.md](references/document-guidelines.md): how to write `flow-map`, `business-rules`, `state-machine`, and `impact-map`.
- [reference-docs-and-dev-handbook.md](references/reference-docs-and-dev-handbook.md): how to match reference-document quality and when to add formulas, tables, glossaries, diagrams, and code-generation examples.
- [existing-knowledge-base-update.md](references/existing-knowledge-base-update.md): how to detect, inventory, merge, and validate existing knowledge bases without destructive replacement.
- [module-knowledge-pack-example.md](references/module-knowledge-pack-example.md): domain-neutral example distilled from a high-density lifecycle reference doc. Use it as a shape and quality example, not as business truth.
- [p0-module-golden-template.md](references/p0-module-golden-template.md): executable golden template for P0/P1 module packs, including required diagrams, evidence tables, async maps, table semantics, and finish checks.
- [quality-checklist.md](references/quality-checklist.md): final coverage checklist for generated knowledge bases and P0/P1 module packs.

## Default Workflow

### 1. Detect Project Facts

Before scanning code, detect whether existing knowledge already exists. If it does, switch to existing-docs-first update mode and inventory the current docs before writing new generated content. See `references/existing-knowledge-base-update.md`.

Collect:

- Build tool: `pom.xml`, `build.gradle`, `build.gradle.kts`, `settings.gradle*`.
- Modules/subprojects.
- HTTP/RPC entrypoints: `@RestController`, `@Controller`, `@FeignClient`, client interfaces.
- MQ consumers/producers.
- Job handlers: XXL-JOB, scheduled tasks, compensation jobs.
- State machines: `State`, `StateFactory`, enum states, strategy factories.
- Core entity states and key enums: status enums, type enums, event enums, review enums, MQ tag enums/constants, amount/discount type enums, business scenario enums.
- Persistence: `Mapper`, `Repository`, `Entity`, MyBatis XML, migrations.
- External dependencies: payment, logistics/shipping, account/user, promotion/coupon, CRM, analytics, inventory/product, Redis/cache, MQ, search, storage, workflow, or other project-specific systems.
- Existing project docs, Yuque exports, PRDs, historical flowcharts, README files, and existing `ai-knowledge-base` directories.

### 2. Run GitNexus For Code Facts

Use GitNexus when available:

```bash
npx -y gitnexus@latest analyze . --skip-agents-md --skip-git --name <project-name>
npx -y gitnexus@latest list
```

Then query candidate areas:

```bash
npx -y gitnexus@latest query "<entry or business term>" -r <project-name>
npx -y gitnexus@latest context <ClassOrMethodName> -r <project-name>
```

Use GitNexus output as candidate evidence, not final truth. Confirm important claims against source files.

Minimum GitNexus usage for each P0/P1 flow:

- Run at least one `query` using the business verb plus suspected entrypoint/class names.
- Run `context` on the main class when GitNexus can resolve it. If exact method context fails, use `query` to find the symbol and then confirm with source reads.
- Record the source-confirmed entrypoint/facade/service/state/strategy/mapper/MQ classes in `flow-map.md` or `diagrams.md`.
- Do not replace GitNexus with only `rg`/manual scanning unless GitNexus is unavailable; if unavailable, state that in the final summary.

### 3. Select Core Flows

Identify P0 core flows by discovering the domain's primary lifecycle verbs and records. In an order-management domain these may be 下单、优惠金额计算、支付、售后、发货; in other domains they may be onboarding, application review, approval, fulfillment, provisioning, settlement, reconciliation, cancellation, renewal, claim handling, or dispatch.

Use the project-specific names from code, API paths, docs, table names, events, and product language. Do not hard-code order-domain flows for non-order projects.

Use the following signals to confirm or add P0/P1 flows:

- State machines: factories, state classes, event/review enums, transition strategies.
- Complex calculation: money, price, discount, quota, stock, capacity, entitlement, risk score, settlement, allocation, refundable amount, carryforward amount, or other business formulas.
- MQ callbacks and async compensation: producer/consumer pairs, delayed messages, idempotency keys, retry jobs.
- Multi-system impact: payment, logistics, promotion, CRM, analytics, account, product, inventory, workflow, Redis/cache, search, file/storage, or other external dependencies.
- Many branches or historical compatibility rules: type-specific behavior, one-to-many/many-to-many relationships, account replacement, legacy state compatibility, platform/channel-specific rules.
- High-risk operations: creation, approval, payment/settlement, refund/reversal, fulfillment, cancellation, close/revoke, state repair, account switching, data import, reconciliation.

Pure CRUD and query endpoints usually belong in a short module README note or `agent-guide/task-routing.md`, not detailed flow docs.

### 4. Build One Integrated Knowledge Base

Generate one integrated `ai-knowledge-base`, not separate "code KB", "reference KB", or "dev handbook" variants.

The default output should merge three layers:

| Layer | Purpose | Content |
|---|---|---|
| Business/reference layer | Preserve domain meaning from reference docs and human-facing documentation. | Scenario granularity, formulas, field semantics, validation lists, status/MQ tables, Mermaid diagrams, and doc-to-code alignment notes. |
| Code navigation layer | Help future agents safely change and debug code. | Entrypoints, services, state machines, MQ/jobs, persistence, impact maps, and stable source evidence. |
| Implementation handbook layer | Teach future agents how to implement in the local project style. | Code-generation rules, table-structure summaries, tag glossaries, MQ/Job/MapStruct examples, and prompt templates. |

Do not make these layers compete. Fold them into the same directory tree and cross-link them from `README.md`, module `README.md`, and `agent-guide/task-routing.md`.

If multiple reference sources exist, first produce a gap analysis:

- What the generated KB already covers.
- What the reference docs cover but the generated KB misses.
- What is code fact vs business wording vs `待人工确认`.

Important distinction:

- The skill's instructions should stay domain-neutral.
- The generated KB should be domain-rich for the current project.
- Do not reduce detail to stay "generic". Generic means the method works for many domains; it does not mean the output should avoid concrete project facts.
- If the project is an account system, document account-specific lifecycle facts. If the project is an order system, document order-specific lifecycle facts. If the project is a workflow system, document workflow-specific lifecycle facts.

### 5. Generate The Knowledge Base

Create or update:

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
├── migration-report.md              # optional; for existing-docs-first updates
├── agent-guide/
│   ├── README.md
│   ├── task-routing.md
│   └── project-facts.md
├── diagrams/
│   ├── README.md
│   ├── module-flow-diagrams.md
│   └── dependency-and-impact-diagrams.md
├── dev-handbook/
│   ├── README.md
│   ├── code-generation-rules.md
│   ├── mq-operation-example.md
│   ├── job-operation-example.md
│   ├── mapstruct-operation-example.md
│   └── prompt-templates/
└── modules/
    └── {module}/
        ├── README.md
        ├── source-docs-map.md        # optional; for modules merged from existing/reference docs
        ├── flow-map.md
        ├── business-rules.md
        ├── state-machine.md
        ├── diagrams.md
        ├── async-map.md
        ├── impact-map.md
        ├── table-structure.md
        └── human-review.md
```

Create files when there is source evidence or useful project convention to record. Empty boilerplate is worse than an omitted file, but the intended shape is integrated:

- Prefer `flow-map.md` that combines business stages, code path, rule branches, state/MQ/DB/external side effects, and source evidence. Only keep separate `business-flows.md`/`code-flow-map.md` when a reference doc or user explicitly requires both views.
- Avoid shallow `code-map.md`. If a navigation map is useful, fold it into module `README.md`, `flow-map.md`, or `agent-guide/task-routing.md` with semantic routing such as "修改某个生命周期阶段读这些 files".
- `state-machine.md`: create when the module has explicit state machines, strategy factories, callback-driven states, review states, or aggregated lifecycle states. Module-level state docs should contain the concrete transition/action details; the top-level `entity-state-and-enums.md` is only the index.
- `diagrams.md`: for P0/P1 modules, prefer module-local diagrams for flow, state, async, data lifecycle, and impact. Top-level `diagrams/` should contain only cross-module overview diagrams.
- `async-map.md`: for modules with MQ, delayed messages, jobs, callbacks, retries, or compensation. Keep global `mq-index.md`/`job-index.md` as indexes, but write module-level async details near the flow.
- `impact-map.md`: for high-risk flows with DB/MQ/external side effects. Make it richer than a summary: include DB writes, MQ producers, known/unknown consumers, external clients, jobs/delayed actions, idempotency keys, failure consequences, and regression checks.
- Top-level `entity-state-and-enums.md`: for core entities with important states or enums; include enum values, business labels, transition constraints, storage fields, and code locations across the project's lifecycle records, callbacks, jobs, and cross-system contracts.
- `diagrams/`: generate cross-module diagrams for core flows, state machines, dependencies, and impact surfaces; detailed module diagrams belong in module `diagrams.md`.
- `table-structure.md`: summarize business semantics and point to Entity/Mapper/XML/migration directories; do not copy full DDL or every field unless a field encodes business rules, formulas, state, idempotency, or historical compatibility.
- Top-level `tags-glossary.md`: business vocabulary, aliases, table labels, cross-system names, search terms, and confusing terms. Explain business meaning first; MQ tag constants belong in `mq-index.md`.
- `dev-handbook/`: when local implementation conventions can be inferred from code or existing docs.

For each P0 module, avoid one-page summaries. Unless the codebase truly lacks evidence, include:

- Scenario list and business boundaries.
- Entrypoint and semantic code navigation.
- Reference-doc-style diagram plan for complex P0/P1 modules: scenario split, validation decision tree, calculation diagram when formulas exist, state swimlane when states exist, variant diagrams for major business branches.
- Mermaid code-chain diagram. Use a swimlane-style `flowchart` with `subgraph` lanes when showing layered code ownership, or a `sequenceDiagram` when call order and request/response timing matter.
- State lifecycle diagram using `stateDiagram-v2` when the module has persisted states or review/callback transitions.
- Data lifecycle/table relationship diagram using `flowchart` or `erDiagram` when table relationships carry business meaning.
- Async diagram using `flowchart` or `sequenceDiagram` when MQ/job/callback/retry exists.
- Impact diagram using `flowchart` for DB/MQ/RPC/cache/job/downstream surfaces.
- Main flow and branch flow tables.
- State/strategy/callback lifecycle table.
- Formula and amount/quantity/resource boundary section when applicable.
- DB table/entity relationship section.
- MQ/job/callback/delayed-message async map when applicable.
- Module-local Mermaid diagrams.
- Impact matrix and regression checklist.
- Specific `待人工确认` items.

For better AI code understanding, include machine-navigable maps:

- Entrypoint-to-service call chains.
- State transition diagrams.
- Entity-state and enum catalogs with exact enum class/file/value names.
- MQ/job producer-consumer maps.
- Table/entity relationship maps.
- Impact maps for DB writes, MQ, external clients, cache, and async jobs.
- Hotspot/risk maps for complex classes, strategy factories, and money/state logic.
- Core-flow rule checklists: preconditions, validation branches, formulas, state changes, side effects, idempotency, and rollback/compensation.

For better human code understanding, include review-oriented views:

- Scenario sequence diagrams with business actor/system boundaries.
- Module responsibility diagrams.
- State lifecycle diagrams with business labels.
- Data lifecycle diagrams for the project's primary business records.
- Change checklists for common tasks such as adding a status, amount field, MQ consumer, or job.

### 6. Write With Evidence

For each claim, prefer stable evidence:

- File path and method/class name.
- Endpoint path.
- Topic/tag or consumer class.
- State enum and state class.
- Entity/Mapper names.
- Enum class, enum value, DB field, factory/strategy class, and transition method names.

For complex links and state machines, include a code-evidence block or table near the business description:

| Business step / rule | Code evidence | Notes |
|---|---|---|
| Human-readable business stage or state transition | `Class.method`, `Enum.VALUE`, `path/to/File.java` | DB/MQ/external side effects or uncertainty |

Use Mermaid for complex flows. Keep prose short and navigational.

When external reference docs are provided, also preserve:

- Business scenario names and ordering.
- Field definitions and compatibility notes.
- Exact formulas and amount-calculation boundaries.
- State transition tables and status meanings.
- MQ topic/tag/producer/consumer contracts.
- Table names and relationship meaning when they encode business rules.
- Source-doc gaps and contradictions as `待人工确认`.

### 7. Finish With A Coverage Summary

Before finishing, run a lightweight quality pass:

- Check that P0/P1 modules have the expected module-pack files or an explicit reason for omission.
- Check Markdown relative links when practical.
- Check that global docs are indexes rather than substitutes for module-level detail.
- Check that `待人工确认` is used for unsupported reference-doc or external-system claims.
- Check that no domain-specific facts from examples were copied into unrelated projects without evidence.

Report:

- Files created/updated.
- Modules covered.
- P0/P1 flows documented.
- Reference docs and existing KBs compared.
- Missing content intentionally added or intentionally deferred.
- GitNexus commands used.
- Items marked `待人工确认`.
- What should be reviewed by product/dev/domain owner.

## Output Quality Bar

- `README.md` is a map, not a manual.
- `context.md` defines domain objects and ID semantics.
- `rules.md` contains hard business rules, formulas, validation conditions, state constraints, idempotency boundaries, and cross-system invariants; avoid generic preferences.
- `flow-map.md` is the default core-flow document. It should combine business-stage view and implementation-path view with evidence.
- `mq-index.md` and `job-index.md` are global.
- `mq-index.md` should include producer, consumer, topic/tag, payload, idempotency key, downstream owner when known, and `待人工确认` when the consumer is outside the repository.
- Module docs must not duplicate global MQ/job indexes.
- `impact-map.md` replaces the vague term “副作用图”; use “影响面图”.
- `impact-map.md` should be a change-risk matrix, not a short list. Include DB/MQ/external/job/cache/analytics/failure/regression columns when evidence exists.
- `tags-glossary.md` explains business vocabulary and search aliases; it is not a duplicate MQ tag table.
- Reference-aligned docs should retain formulas, field semantics, state/MQ tables, and scenario-specific rules instead of collapsing them into one-line summaries.
- Dev-handbook docs should include actionable implementation conventions and examples, not just where code lives.
- Human questions must be specific and answerable.
