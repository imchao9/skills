# Codex adapter for pstack-style orchestration

This adapter preserves pstack's useful ideas—coordinator, bounded units, parallel workers, verifier, ledger, and stop/replan rules—without depending on Cursor commands such as `/poteto-mode`, `Task`, `orch`, or Cursor plugins.

## Mapping

| pstack concept | Codex implementation |
|---|---|
| `/poteto-mode` | `software-factory/SKILL.md` plus the repository's `AGENTS.md` contract |
| `feature` / `orchestrate` playbook | the stage table in `SKILL.md` and `factory.py` state files |
| Cursor `Task` / subagent | a Codex local or cloud thread created from a worker brief |
| `units.tsv` frontier | `docs/factory/<work-id>/units.tsv` |
| verifier ledger | append-only `ledger.jsonl` plus `receipts/` |
| inbox / decisions | `inbox/` and `decisions.md` in the same work directory |
| Cursor model/plugin | the Codex model and committed skills selected by the main agent |
| Comment Sicko / interrogate | independent review brief using `code-review` and project verification |

The adapter is intentionally artifact-first. The main agent does not keep the entire state in chat history. A cloud worker can resume from the committed intent, plan, unit brief, and receipts after an isolated workspace is created.

## Worker lifecycle

1. **Pilot**: dispatch one small vertical slice. Confirm that the acceptance and verification commands produce useful evidence.
2. **Scale**: dispatch independent units to separate Codex workers. Each worker owns a narrow scope and writes one receipt.
3. **Drain**: wait for dependencies, re-run failed verification, and replan units whose assumptions changed.
4. **Land**: the main agent reviews the combined diff and asks for merge/deploy authorization when required.
5. **Close**: write the final receipt and a short retro. Promote a repeated correction into a hook, lint, test, or skill only when the evidence supports it.

## Codex Cloud boundary

The cloud task prompt must include the work-id and exact file paths. It may run repository commands and edit code in its isolated workspace. It must not rely on local `~/.agents/skills`, browser/computer access, uncommitted secrets, or another worker's uncommitted files. For UI work, split the task: cloud implements deterministic code and test hooks; the local verifier runs the real browser/device checks and records screenshots or video.

## Minimal task brief

```text
WORK_ID: checkout-search-001
ROLE: implementer
GOAL: Add server-side filtering to the checkout search endpoint.
BASE: Read docs/factory/checkout-search-001/intent.md, spec.md, plan.md.
SCOPE: src/search/**; tests/search/**
READ: docs/factory/checkout-search-001/units.tsv; verify.md
SKILLS: implement, tdd
ACCEPTANCE: ...
VERIFY: npm test -- search; npm run typecheck
FORBIDDEN: no schema migration, no dependency upgrades, no deploy
TIMEBOX: one focused pass; stop on missing contract
REPORT: changed files, commands/results, unresolved risks, next unit
```

