---
name: ai-test-doc-drift-audit
description: Use when auditing ai-intelligent-test documentation, README structure, AGENTS rules, agent docs, skills, examples, or onboarding commands for drift against the current repository structure, canonical platforms, configured projects, formal case assets, and TS-first delivery rules.
---

# AI Test Doc Drift Audit

Use this skill to run a report-only drift audit for `ai-intelligent-test`. Treat the repository as the source of truth, and make every finding usable as follow-up repair context.

## Output Language

Default to Chinese for the final audit report unless the user explicitly asks for another language. Keep stable identifiers, file paths, field names, and shell commands in their original form when that makes follow-up fixes easier.

## Quick Start

Run the default report command for normal use:

```bash
node .agents/skills/ai-test-doc-drift-audit/scripts/doc-drift-audit.mjs
```

Use JSON only when automation or another script needs structured data:

```bash
node .agents/skills/ai-test-doc-drift-audit/scripts/doc-drift-audit.mjs --json
```

Treat the script output as deterministic facts and candidate findings only. Before presenting results, inspect the cited files and complete the Manual Review Checklist; the agent owns final priority judgment and wording.

## Mandatory Agent Review

The script is the baseline, not the audit. Do not treat zero script findings as full clearance.

For every audit:

- Run the default script when feasible, then manually inspect the relevant Audit Scope files.
- Run targeted `rg` searches for drift-prone terms such as `h5`, `pc`, `desktop`, `YAML`, `source-excel-runtime`, `runtime fallback`, `Sealos`, `tanyue-h5`, and `tanyue`.
- Check whether the wording, emphasis, and examples would steer a new teammate or future agent toward the wrong platform, path, case format, or delivery workflow.
- Distinguish `Deterministic scan` findings from `Manual semantic review` findings in the final report.
- If the manual review was intentionally shallow or time-limited, include the residual risk instead of declaring the documentation fully clean.

## Audit Scope

Check these surfaces together:

- `README.md` project tree, supported-project summary, and common command examples
- `AGENTS.md`, especially platform names, TS-first rules, and GUI runtime boundaries
- `docs/agent/*` and project docs that teach agent behavior
- `.agents/skills/*`, especially workflow references that future agents may follow
- `midscene.config.ts`, `src/core/platform.ts`, `package.json`, and real `cases/` directories

Primary truth hierarchy:

1. `src/core/platform.ts` for canonical platform names
2. `cases/<platform>/<project>/` for real formal case asset locations
3. `midscene.config.ts` for config-supported project/platform combinations
4. `AGENTS.md` and `docs/agent/*` for agent delivery contracts
5. `knowledge/` for historical recall, not runtime or delivery truth

## What The Script Detects

The bundled script reports deterministic findings for:

- README tree entries that do not exist under `cases/`
- `cases/` project directories missing from the README tree
- README maintained-asset lists that omit or overstate formal `.ts/.yaml/.yml` assets
- common command examples that point at config-only, empty, unknown, or non-canonical targets
- legacy wording such as `type: h5`, `platform: h5`, `platform: pc`, `platform: desktop`, stale Sealos headings, old YAML-first headings, and loose runtime fallback wording

The script intentionally does not:

- automatically edit files
- treat every `h5`, `desktop`, `YAML`, or `source-excel-runtime` mention as wrong
- decide whether historical `knowledge/` content should be deleted
- run business test cases

## Report Contract

When presenting results, preserve the repair context from each finding:

```text
source
id
priority
file:line
stale_claim
current_truth
why_it_matters
suggested_fix
verification
```

Use this code-review-style priority guide:

- `P0`: audit output is structurally wrong or a doc rule would cause broad destructive behavior, broken generation paths, or unusable automation
- `P1`: directly steers agents to wrong platform names, wrong generated paths, YAML-first formal cases, or GUI runtime fallback as a coding-agent completion path
- `P2`: misleading README structure, stale command examples, stale supported-project lists, or docs that make onboarding materially worse
- `P3`: low-risk wording cleanup, explicitly historical context, or compatibility notes that should not drive current agent behavior

## Manual Review Checklist

After reading the script output, verify:

- Is the cited claim current guidance, or explicitly historical knowledge?
- Does a command example target a formal maintained suite, or only a configured project?
- Does a README tree entry describe real directories, not just config support?
- Does any doc weaken the rule that formal generated business cases default to TypeScript `ScriptTestCase`?
- Does any doc imply `source-excel-runtime` is a coding-agent delivery path instead of a GUI/packaged-runner implementation detail?

If the user asks for fixes, patch only the cited docs unless the finding proves a framework-level change is required.
