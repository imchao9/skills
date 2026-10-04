---
name: software-factory
description: Orchestrate a repository change from intent through verified delivery using committed factory artifacts, Codex local/cloud workers, and explicit human gates.
---

# Software factory for Codex

Use this skill when a request spans requirements, design, implementation, verification, or a pull request. Treat the repository's `docs/factory/<work-id>/` directory as the durable handoff between the main agent, cloud workers, and verifiers.

## Operating model

The main agent is the coordinator. It owns the user's intent, chooses the stage, creates the next artifact, and decides whether a gate is passed. A worker may edit code only inside its assigned scope. A verifier produces evidence; it does not mark its own work as accepted. Human input is required only for product direction, visual direction when ambiguity matters, irreversible external actions, and the final merge/deploy decision.

Do not load every available skill. Route only the stage that is active:

| Stage | Load these skills | Primary target | Required artifact |
|---|---|---|---|
| Intake | `grill-with-docs`, `grill-me`, `research` | local main agent | `intent.md` |
| Design | `domain-modeling`, `codebase-design`, `prototype` when UI is material | local main agent; cloud may inspect code | `spec.md`, `design.md` |
| Tickets | `to-spec`, `to-tickets`, `wayfinder` | local main agent or cloud planner | `plan.md`, `units.tsv` |
| Verification setup | project `verify-<app>` skill; `create-verification-skill` if absent | local for browser/device, cloud for CLI setup | `verify.md` and executable checks |
| Execute | `implement`, `implement-spec`, `tdd`; pstack feature/orchestrate method | Codex Cloud by default | code, tests, worker receipt |
| Diagnose | `diagnosing-bugs`, `tdd` | cloud for reproducible CLI bugs; local for live UI | incident note, regression test |
| Review | `code-review`, pstack interrogate/blast-radius methods | cloud for static/test review; local for live UI | `REVIEW.md` |
| Ship | `pr`, `retro` | local main agent | PR evidence, decision/retro |

## Codex handoff

Before delegating, create a worker brief with these fields: `GOAL`, `BASE`, `SCOPE`, `READ`, `SKILLS`, `ACCEPTANCE`, `VERIFY`, `FORBIDDEN`, `TIMEBOX`, and `REPORT`. A cloud worker receives the brief plus the repository; it must read the committed factory artifacts before editing. It reports changed files, commands, results, failures, and follow-up risks in a receipt.

Cloud workers are suitable for repository inspection, specification/ticket refinement after direction is settled, implementation, unit/integration/static verification, and reproducible CLI/API bug fixes. Keep product decisions, private local memory, browser/computer interaction, visual review, and merge/deploy authorization with the local main agent. Personal skills outside the repository are not available to a cloud worker; commit the required skill or put its essential contract in the brief.

## Gates and stop rules

1. Do not execute before `intent.md`, `spec.md` (when design is non-trivial), `plan.md`, and `units.tsv` exist.
2. A unit is ready only when its acceptance and verification commands are concrete.
3. Stop and return to the main agent when scope is missing, acceptance is contradictory, verification is unavailable, a worker touches files outside scope, or a test fails for an unexplained reason.
4. A green worker report is not acceptance. The independent verifier must rerun the checks and attach evidence.
5. Never merge, deploy, send external messages, or change credentials from a worker brief unless the user has explicitly authorized that action.

## Durable state

Use `scripts/factory.py` to create and inspect the state directory. Keep `units.tsv` as the work frontier and append events to `ledger.jsonl`; do not rewrite history. Receipts belong under `receipts/`, and unresolved choices belong in `decisions.md`.

To install only the skills needed for a project stage or domain, run `factory.py activate` with `--skills-repo`, `--stage`, and optionally `--pack` (or explicit `--skill` names). Packs are declared in `software-factory-set.json`; a frontend project can use `--pack frontend`, while a Java service can use `--pack backend-java`. It refuses to overwrite an existing project skill unless `--replace` is supplied. This keeps the catalog installed once while keeping each project's active surface small.
