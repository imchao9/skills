---
name: ai-test-goal-workflows
description: Goal-mode workflows for ai-intelligent-test. Use when Codex is asked to run project work as a Goal, generate or execute tests from a code diff or PR, produce a Coverage Review before generating diff-based cases, use test pass plus code review as acceptance gates, or convert QA-provided Excel/XMind/test-case assets into executable cases while preserving the source as the oracle.
---

# AI Test Goal Workflows

Use this skill to choose the right Goal contract before test-generation or test-execution work in `ai-intelligent-test`.

## Decision Router

- **Development diff acceptance**: use when the user mentions current diff, PR diff, code changes, coverage review, code quality acceptance, double gate, "目标模式", or generating tests from implementation changes. Read `references/diff-acceptance.md`.
- **QA oracle conversion**: use when the user provides Excel, XMind, test-case tables, QA-authored cases, test points, or says to trust the supplied test cases. Read `references/qa-oracle-conversion.md`.

If both apply, handle QA oracle conversion first for the supplied case assets, then use diff acceptance only for code changes made to support those cases.

## Required Context

1. Read `AGENTS.md` and `docs/agent/runbook.md`.
2. Read `docs/agent/goal-workflows.md`.
3. Read the reference file selected by the router above.
4. For any business case generation, repair, debugging, or batch run, invoke `test-knowledge-recall` before editing cases or support helpers.
5. Read nearby `cases/`, `cases/support/`, `knowledge/`, and recent `midscene_run/report/` or `midscene_run/cache/` artifacts for the target platform/project/domain.

## Core Rules

- In development diff mode, treat `diff is signal, not truth`; first produce a Coverage Review for human review, then generate tests for approved TC items. Completion requires the Coverage Review gate, Test gate, and Review gate to pass.
- In QA oracle mode, treat `test case is truth`; preserve the original row order, steps, expected results, endpoints, fixtures, and blocker semantics.
- Generate formal maintained cases as TypeScript `ScriptTestCase` files unless the user explicitly asks for YAML.
- When the target project has `docs/agent/projects/<project>.md`, enforce that project doc during maintained case generation and execution.
- Keep execution-critical behavior in `cases/` or `cases/support/`; use `knowledge/` only for recall, source notes, page maps, test data references, and failure memory.
- Do not mark a Goal complete from partial evidence. If tests cannot run, review has blocking findings, source cases are ambiguous, or required data/auth is missing, stop with the evidence and exact unblocking input needed.
