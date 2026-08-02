---
name: ai-test-run-diagnosis
description: Use when running or verifying existing ai-intelligent-test cases, inspecting failed or suspicious run reports, deciding whether the target state was actually reached, or classifying why a run did not provide valid business evidence.
---

# AI Test Run Diagnosis

Use existing run artifacts to separate “the runner finished” from “the business behavior was verified.” This skill is report-first and read-only: do not change cases, framework code, report files, or product code while diagnosing.

## Workflow

1. Read `AGENTS.md`, `docs/agent/runbook.md`, and the relevant case/project guidance.
2. Select one exact run directory. Prefer an explicit path supplied by the user or produced by the current run. Never silently diagnose `latest`.
3. Extract deterministic facts:

   ```bash
   node .agents/skills/ai-test-run-diagnosis/scripts/summarize-run.mjs \
     --report midscene_run/report/<run-id>
   ```

   For one case in a batch, add `--case <case-id>`. Use `--json` only for machine consumption. `--since <ISO timestamp>` is allowed only when exactly one report was created in that window.
4. Open the final screenshot and any failure-related trace, video, sensor log, or Midscene report needed to judge the target. The script checks existence and metadata; it does not understand the business screen.
5. Judge the four axes and overall verdict using [verdict-model.md](references/verdict-model.md).
6. Classify a non-pass only after inspecting evidence. Use [failure-taxonomy.md](references/failure-taxonomy.md); do not infer `product` from `ai_assert_failed` or `framework` from `runtime_error`.
7. Return the result using [output-contract.md](references/output-contract.md).

## Hard Gates

- A process exit code, generated HTML, `manifest.status=passed`, or screenshot-audit pass is not by itself business proof.
- Any `failed`, `error`, `skipped`, missing case, missing evidence file, missing/blank final screenshot, or unparsed failure evidence blocks `VERIFIED_PASS`.
- `skipped` means not verified even if the CLI exited successfully.
- If the target page/state cannot be seen, set target status to `unknown` and overall verdict to `INVALID_RUN` or `INCONCLUSIVE`.
- State unknowns explicitly. Never promote an inference to an observed fact.

## Scope Boundary

This skill adjudicates a completed run. It does not:

- generate or repair cases;
- modify framework/report behavior;
- submit metrics;
- claim root cause without evidence;
- write diagnosis artifacts into the report directory.

If the user asks to repair or debug a business case after triage, switch to `test-knowledge-recall` before editing and follow the repository knowledge-sedimentation rule afterward.
