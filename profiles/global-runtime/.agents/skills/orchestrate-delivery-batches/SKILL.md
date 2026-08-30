---
name: orchestrate-delivery-batches
description: Orchestrate complex delivery work into a reviewed plan, vertical tickets, dependency-aware batches, model and agent assignments, and integration gates. Use when the user asks to plan first, split tickets, choose models, delegate subagents, parallelize implementation, supervise a long-running task, or keep several core chains moving without context rot.
metadata:
  x-provenance: local
  x-owner: cm
  x-source-note: created from the local plan-ticket-model-batch delivery workflow
---

# Orchestrate Delivery Batches

Turn a large request into a controlled **delivery frontier**: plan the outcome, split complete vertical slices, route each slice to the cheapest capable model, execute only unblocked batches, and integrate under one done contract.

Do not use this process for a small single-file change, a simple answer, or work with no useful decomposition. Do not create agents merely to appear parallel.

## 1. Lock the delivery contract

Read the repository instructions and current implementation before drafting work. Record:

- objective and user-visible outcome;
- scope and explicit exclusions;
- the main end-to-end chains;
- current evidence, known gaps, and external dependencies;
- a done contract separating local code, automated verification, deployment, upstream readback, and human or现场验收;
- authorization boundaries for issues, commits, pushes, deployment, production data, and external messages.

If a missing choice changes an external contract or risk, stop and ask. Otherwise make a reversible assumption and label it.

Completion criterion: every requested outcome maps to one chain and one verifiable done condition; no deployment or现场状态 is represented as locally complete.

## 2. Create the plan artifact

For work expected to span several tickets or agent contexts, create or update one plan document in the repository's normal planning location. If the user asked only to review or confirm a plan and did not ask for a file, keep the first draft in the response until confirmed. If a file is authorized and no planning location exists, use `docs/plans/<feature-slug>.md` when appropriate; otherwise keep the plan in the current task and state why no file was created.

Use [the plan and dispatch template](references/plan-and-dispatch-template.md). Keep one source of truth: update this plan rather than creating a new plan per batch.

Completion criterion: the plan contains the contract, vertical chains, dependency graph, batch order, model routing, verification gates, and a live progress ledger.

## 3. Split tracer-bullet tickets

Each ticket must be a narrow, complete vertical slice through every required layer. It must:

- produce a demoable or independently verifiable outcome;
- fit in one fresh agent context;
- declare genuine blocking edges;
- state acceptance criteria and the strongest available automated check;
- separate external or human acceptance from code completion;
- avoid stale implementation paths in tracker text.

Keep wide mechanical refactors separate and sequence them expand → migrate → contract. Work the **frontier**: only tickets whose blockers are complete may start.

When another explicitly invoked ticket skill owns tracker publication, let it publish the approved tickets; this skill retains ownership of the dependency graph, model routing, and batch ledger. External issue creation still requires user authorization.

Completion criterion: every scope item belongs to exactly one ticket or an explicit integration ticket, and every ticket is independently grabbable.

## 4. Route models and roles

Inspect the models, reasoning levels, roles, concurrency slots, and tool constraints available in the current runtime. Do not assume yesterday's model list is still valid.

Choose the cheapest model tier that can safely close the ticket:

- strongest frontier reasoning: contracts, architecture, migrations, concurrency, security, external protocols, cross-cutting state machines, and final integration;
- balanced agentic model: bounded product slices with clear contracts and ordinary frontend/backend work;
- fast or cost-efficient model: read-only exploration, mechanical edits, test execution, inventories, and documentation;
- reviewer/verifier role: independent bug finding or acceptance; never let the implementer self-certify a high-risk slice when an independent role is available.

Honor an explicit user model choice. Otherwise inherit the parent model unless an override has a concrete quality, latency, or cost benefit. When the runtime only permits overrides with limited or empty inherited context, include all required contracts and evidence in the dispatch brief.

Record the chosen model tier and one-line reason for every ticket. See [model routing](references/model-routing.md) for current-family examples.

Completion criterion: every frontier ticket has an owner role, model tier, reason, and acceptance gate; no ticket is routed only by perceived model prestige.

## 5. Confirm before execution when requested

Present the plan, ticket graph, batches, model choices, and unresolved risks in a compact table. If the user asked to confirm first, pause before publishing tickets, editing implementation code, or dispatching workers. Planning artifacts and read-only exploration remain allowed.

If the user already authorized continuous execution, proceed without asking again, but do not infer permission for commit, push, deploy, production writes, or other external mutations.

Completion criterion: the user's confirmation requirement is satisfied and the authorized mutation boundary is explicit.

## 6. Dispatch dependency-aware batches

Use subagents only when the user, repository instructions, or an applicable skill authorizes delegation.

- Assign one ticket or one sharply bounded responsibility per agent.
- Declare file/module ownership in the dispatch brief after code exploration, even though tracker tickets remain implementation-path agnostic.
- Tell workers they share the codebase, must preserve unrelated edits, and must not revert other agents.
- Dispatch independent frontier tickets in parallel within available slots.
- Keep blocked tickets queued; do not start speculative downstream work.
- Keep the primary agent as integrator: review diffs, resolve shared contracts, update the plan, and open the next frontier.
- Prefer a fresh context for each batch. Pass the plan path, ticket contract, dependencies, owned files, verification command, and stopping boundary—not the full conversation by default.

Completion criterion: every running agent owns a non-overlapping bounded slice, and every dispatched slice was unblocked at dispatch time.

## 7. Supervise, integrate, and advance

After each batch:

1. collect agent results and actual changed files;
2. run the ticket's acceptance checks;
3. independently review risky changes;
4. fix integration regressions before opening more downstream work;
5. update ticket status, evidence, blockers, and the plan ledger;
6. dispatch the newly opened frontier.

Do not poll agents aggressively or narrate unchanged waits. If one agent becomes blocked, continue independent frontier work while preserving the blocker as a real status.

Completion criterion: the integrated branch is green at the batch gate and the plan ledger matches actual code and ticket state.

## 8. Close against the done contract

Run the repository's full required verification plus independent acceptance proportional to risk. Report separately:

- implemented and locally verified;
- integrated and regression-tested;
- committed or pushed;
- deployed and health-checked;
- upstream read back;
- ready for human or现场验收;
- blocked, with the exact missing authority or evidence.

Never close tickets merely because agents returned. Never label simulation, HTTP success, or model inspection as a real upstream or现场 result.

Completion criterion: every ticket has evidence for its declared acceptance level, no required work remains hidden, and any remaining human/external gate is explicitly open.
