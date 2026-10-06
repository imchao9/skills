---
name: workflow-packaging-audit
description: Use when asked to review recent Codex sessions, Memories, Chronicle, existing skills, custom agents, or automations to identify repeated manual workflows and decide whether to create the smallest useful skill, subagent, automation, extension, or skip.
x-provenance: local
x-owner: cm
x-source-note: created from local workflow
---

# Workflow Packaging Audit

Use this skill to turn repeated work into the smallest reusable asset. The output should be evidence-led and conservative: prefer reuse, extension, or skip over creating broad new assets.

## Evidence Order

1. Recent Codex sessions and task summaries from the last 30 days, or all available history if shorter.
2. Codex Memories and rollout summaries for cross-session patterns.
3. Chronicle only if enabled. Use it for discovery, then confirm important details in the source system when practical.
4. Existing skills, custom agents, and automations, so new work does not duplicate current assets.

If evidence is missing or stale, say so and continue with the strongest available source. Do not present discovery-only evidence as confirmed-current.

## Candidate Test

Only act on a workflow when all of these are true:

- It occurred at least twice, or is clearly likely to recur and costly to repeat.
- It has stable inputs, a repeatable procedure, and a clear output or stopping condition.
- Packaging it would materially improve speed, quality, consistency, or reliability.
- It is not already adequately covered by an existing skill, agent, automation, script, or documented runbook.

Skip candidates that are one-off, ambiguous, sensitive, poorly evidenced, or mainly require human judgment without a stable procedure.

## Choose The Smallest Form

- **Skill**: reusable workflow, playbook, decision guide, or source-aware procedure.
- **Custom subagent**: bounded specialist role suitable for delegation, such as repeated investigation or review passes.
- **Automation**: scheduled report, reminder, monitor, or recurring check with safe, stable outputs.
- **Extend existing**: when an existing asset mostly covers the workflow.
- **Skip**: when evidence or value is insufficient.

Default to a skill for judgment-heavy audits. Default to automation only when the task is report-only or monitoring-oriented and safe to run unattended. Never create an automation that mutates files, config, or external systems unless the user explicitly asks for that.

## Required Output

First produce a compact shortlist with:

- repeated workflow
- supporting evidence and dates
- frequency/confidence
- recommended form
- why it is or is not worth creating

Then create only high-confidence missing items. Keep each asset narrow, practical, source-aware, and easy to validate. Do not create speculative, overlapping, or overly broad assets.

Finish with:

- what was created or extended
- what was deliberately skipped
- what needs more evidence before packaging

## Creation Rules

- Before creating a skill, read `skill-creator` guidance and keep `SKILL.md` concise.
- Before creating or updating an automation, use the automation tool and prefer report-only behavior unless the user asked for action.
- Before creating a custom subagent, confirm no existing skill or general delegation pattern already covers it.
- Validate created assets with lightweight structural checks and a discoverability check.
- Do not include secrets, full MCP URLs with keys, cookies, private tokens, or sensitive personal data in created assets or summaries.
