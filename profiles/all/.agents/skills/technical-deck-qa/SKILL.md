---
name: technical-deck-qa
description: Use when asked to do a read-only QA or reviewer pass on a generated technical presentation, HTML/PDF/PPT deck, slide screenshots, style reference, visual QA report, or technical demo narrative. Focus on whether the deck works for a technical lead, evaluator, or stakeholder; compare against evidence and references; do not generate or modify the deck unless explicitly asked.
x-provenance: local
x-owner: cm
x-source-note: created from local presentation review workflow
---

# Technical Deck QA

Use this skill as a read-only review pass after a deck has been generated.
The job is to decide whether the artifact is credible, inspectable, and aligned
with the requested style or technical goal.

## Workflow

1. Inventory the evidence first.
   - List the deck/source file, screenshots or rendered pages, style/reference docs, QA reports, speaker notes, and generation plan.
   - If screenshots or rendered pages exist, inspect them visually. Do not rely only on markdown or JSON summaries.
   - If a reference style is provided, inspect representative reference pages and compare layout behavior, not just color.

2. Review from the target evaluator's perspective.
   - For technical leads: check claim specificity, system boundaries, architecture clarity, risk handling, and whether diagrams support decisions.
   - For product or business stakeholders: check narrative progression, audience fit, evidence density, and actionability.
   - For visual/style QA: check hierarchy, whitespace, typography, grid, contrast, figure legibility, slide-to-slide rhythm, and whether the reference is actually implemented.

3. Separate blockers from polish.
   - Blockers are issues that would make the deck misleading, untrusted, unreadable, or visibly off-brief.
   - Improvements are changes that strengthen clarity, pacing, visual polish, or evaluation confidence.
   - Avoid generic praise. Anchor every finding in a specific page, screenshot, file, or repeated pattern.

4. Preserve the read-only boundary.
   - Do not modify files, regenerate slides, start long renders, or touch external systems unless the user explicitly changes scope.
   - Do not expose private notes, hidden prompts, or sensitive document contents beyond short, necessary summaries.

## Output Shape

Lead with the decision:

- `pass`: acceptable as-is for the stated audience.
- `conditional pass`: usable after specific fixes.
- `fail`: not ready for the stated audience or reference target.

Then provide:

- `top findings`: ordered by impact, with page/file evidence.
- `reference alignment`: where it matches and where it diverges.
- `specific fixes`: concrete next edits, not vague design advice.
- `residual risk`: what was not verified, such as missing pages, absent speaker notes, or no rendered screenshots.

Keep the response compact unless the user asks for a full slide-by-slide audit.
