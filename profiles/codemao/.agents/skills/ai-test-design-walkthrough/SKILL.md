---
name: ai-test-design-walkthrough
description: Use when executing a registered ai-intelligent-test design or interaction walkthrough, comparing a maintained Figma baseline with the real application, validating walkthrough evidence, or reporting visual review findings through the existing report system.
---

# AI Test Design Walkthrough

Run the repository's maintained design-review cases through the existing bridge, runner, evidence model, and HTML reporter. This skill is an entry and evidence gate, not a second test framework or report system.

## V1 Boundary

- Only use formal cases returned by `list`. The case registry owns the Figma URL and node id.
- Do not accept an arbitrary Figma source, transient case, or Excel runtime row.
- Reuse `desktop/bridge.ts`, `runRuntimeCaseSuite`, `manifest.json`, `ReportEvidence`, `design-walkthrough.json`, and the existing `index.html`.
- Keep this skill independent from `ai-test-run-diagnosis`; apply the design-specific target/evidence gate below.
- Treat maintained `version: 4` templates as judgment contracts only. Reject templates containing runtime `observed`, status, confidence, issues, findings, recommendations, or conclusions.
- Require every checkpoint to bind a Figma root, actual root, and allowlisted key targets with stable actual anchors. Missing anchors must degrade visibly; AI auto-match is not high-confidence evidence.

## Workflow

1. Read `AGENTS.md`, `docs/agent/runbook.md`, `docs/agent/design-walkthrough.md`, and the target project guidance.
2. List the registered formal cases:

   ```bash
   node .agents/skills/ai-test-design-walkthrough/scripts/run-design-walkthrough.mjs list
   ```

3. Select the exact case id and preflight it:

   ```bash
   node .agents/skills/ai-test-design-walkthrough/scripts/run-design-walkthrough.mjs \
     preflight --case <case-id>
   ```

   Stop on any blocking issue. Configure model/Figma credentials and runtime paths through `.env` or the process environment; never put them in command arguments.
4. Run the same registered case:

   ```bash
   node .agents/skills/ai-test-design-walkthrough/scripts/run-design-walkthrough.mjs \
     run --case <case-id>
   ```

   Optional non-secret overrides are `--package-name`, `--course-name`, `--link-name`, `--notes`, `--expected-variance`, and `--viewport <width>x<height>`.
5. Inspect the emitted `design-walkthrough-acceptance` event and the report itself. Follow [evidence-gates.md](references/evidence-gates.md). For each reached checkpoint verify that the report shows separate deterministic status, visual status/coverage, conflicts, fusion reason, and overall status.
6. Confirm that `design-spec.json` revision matches the runtime-injected Figma artifact, and that the template had no prefilled run conclusions.
7. Present the existing report path, target state, overall design verdict, checkpoint exceptions, actionable issues, unknowns, and rerun advice. Do not collapse `DESIGN_REVIEW_ADJUST`, `DESIGN_REVIEW_NEEDS_REVIEW`, and `DESIGN_REVIEW_UNKNOWN` into a generic test failure.
8. Apply the repository knowledge-sedimentation rule only when the run produced reusable product/design knowledge.

## Credential And Input Safety

The wrapper creates a mode-`0600` payload under the system temporary directory, removes it on success, failure, or termination, and filters model/Figma secret values from child output. It takes the Figma source from the maintained registry.

Model API keys and `FIGMA_ACCESS_TOKEN` must not be stored in source, knowledge, reports, or logs. Test-environment accounts and business fixtures remain governed by the repository's test-data fidelity rule.

## Completion Rule

A bridge exit alone is not completion. The acceptance event must show:

- the formal case passed execution;
- `manifest.json`, `ui-audit.json`, `design-walkthrough-input.json`, `design-spec.json`, `design-walkthrough.json`, and `index.html` exist;
- final screenshot evidence exists;
- `target.targetReached` is true;
- the overall design verdict is present and not `DESIGN_REVIEW_UNKNOWN`.
- each reached checkpoint has independent visual target coverage and deterministic comparison output;
- hard-fact and measurement conflicts are resolved by the code state machine, not by a model-authored final status.

Checkpoint-level unknowns remain visible and require follow-up, but a valid overall `PASSED`, `ADJUST`, or `NEEDS_REVIEW` verdict can complete the walkthrough.
