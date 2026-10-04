---
name: ai-intelligent-test
description: Route Codex into the internal ai-intelligent-test framework from any project. Use when the user asks Codex to generate or run maintained AI Test cases, convert QA cases to TypeScript, review coverage from a diff or PR, diagnose AI Test reports, execute registered design walkthroughs, collect AI Test metrics, or decide whether Midscene model configuration is required.
---

# AI Intelligent Test

Use this as the portable entrypoint. Keep the internal repository as the
execution and asset source of truth; do not copy its framework code or cases
into the target product repository.

## Resolve the framework

1. If the current repository's `package.json` name is `ai-intelligent-test`,
   use the current root.
2. Otherwise check an explicit `AI_INTELLIGENT_TEST_ROOT`.
3. Otherwise search only the user's normal code roots for a checkout whose
   origin is
   `git@gitlab.codemao.cn:frontend/student/ai-intelligent-test.git`.
4. If no checkout exists, ask before cloning the canonical repository.
5. Read that checkout's `AGENTS.md` and required repository documents before
   editing or running anything.

Run all framework-relative commands with the resolved framework root as the
working directory. Treat the user's current repository as the target product
repository unless the request says otherwise.

## Route the request

- Requirement, QA Excel/XMind, diff, PR, Coverage Review, or maintained case
  generation: read and follow
  `<framework>/.agents/skills/ai-test-goal-workflows/SKILL.md`.
- Existing run or report diagnosis: read and follow
  `<framework>/.agents/skills/ai-test-run-diagnosis/SKILL.md`.
- Registered Figma/design walkthrough: read and follow
  `<framework>/.agents/skills/ai-test-design-walkthrough/SKILL.md`.
- Knowledge recall before generating, repairing, or debugging a business
  case: read and follow
  `<framework>/.agents/skills/test-knowledge-recall/SKILL.md`.
- Documentation drift: read and follow
  `<framework>/.agents/skills/ai-test-doc-drift-audit/SKILL.md`.
- Metrics preparation or submission: only when explicitly requested, read and
  follow `<framework>/.agents/skills/ai-test-metrics/SKILL.md`. Preserve its
  fixed-DingTalk write boundary and approval rules.

## Choose the execution backend

Read [execution-backends.md](references/execution-backends.md) whenever the
request asks whether model configuration can be omitted or asks Codex to
operate the UI directly.

- Use `framework-only` for planning, case generation, code edits, deterministic
  scripts, report parsing, and documentation audits.
- Use `midscene` for maintained visual execution, `aiAct`, `aiAssert`,
  cross-platform runners, cache, evidence, and official HTML reports.
- Use `codex-native-spike` only for explicit, temporary exploratory UI checks.

Never report a Codex-native spike as an AI Test framework run. Never claim
Midscene evidence, cache, report, or device coverage when the Midscene runner
did not execute.

## Completion

Return:

- resolved framework and target-product roots;
- selected inner workflow and backend;
- whether model credentials were required;
- created/changed maintained assets;
- executed checks and report paths;
- blockers, unknowns, and whether any run was only a transient Codex-native
  spike.
