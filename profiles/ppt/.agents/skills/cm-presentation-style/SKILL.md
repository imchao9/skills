---
name: cm-presentation-style
description: Create or evaluate CM-style presentation artifacts. Use when generating, improving, or reviewing internal technical review decks, PPT-like HTML presentations, external promotional HTML presentations, personal presentation style guides, deck scorecards, or reusable presentation profiles.
x-provenance: local
x-owner: cm
x-source-note: created from local presentation style experiments
---

# CM Presentation Style

Use this skill as the style-control layer before calling renderers such as `humanize-ppt`, `html-ppt`, `fireworks-tech-graph`, `guizang-ppt`, or PPTX generators.

## Workflow

1. Classify the artifact:
   - Internal technical review deck: read `references/internal-tech-review.md`.
   - External promotional HTML presentation: read `references/external-promo-html.md`.
   - If both are requested, produce both from a shared claim/source ledger but with separate layouts and calls to action.
2. Build the structure before visual design:
   - audience, meeting goal, state shift, core argument, claims, assumptions, decision asks.
   - diagram inventory: architecture, flow, data/event path, comparison, roadmap.
3. Apply the CM visual language from `references/visual-language.md`.
   - For external-facing report or promo style inspired by Google AI responsibility reports, also read `references/google-ai-report-style.md`.
   - For general slide quality practices and review criteria, read `references/presentation-practice-patterns.md`.
   - For Adobe, Google Slides, Microsoft PowerPoint, Canva, Pitch, Beautiful.ai, or template-platform inspiration, read `references/presentation-platform-references.md`.
4. Render the artifact using the most appropriate deck or HTML skill.
5. Run QA:
   - renderer checks: slide count, screenshots, image load, dimensions.
   - review checks: use `references/scorecard.md`.
   - static helper: `scripts/score_deck_static.py`.
6. Save scorecard results next to the run artifact. Do not call the artifact done when it only passes screenshot checks.

## Required Outputs

For each serious run, create or update:

- `slide_plan.json`: page intent, visible points, notes target, media needs.
- `claim_ledger.md`: claim, source, assumption, confidence, risk if challenged.
- `diagram_spec.md`: node/edge semantics, read order, legend, invariants.
- `style_brief.md`: selected mode, visual language, density, color usage.
- `qa_report.md`: renderer checks plus review scorecard.
- screenshots for every page at 1920x1080.

## Quality Bar

A CM-style presentation should be decision-oriented, visually restrained, and source-grounded.

Avoid:

- decorative slides that do not help decision-making.
- one-note color palettes.
- raw architecture diagrams copied from source docs without presentation redesign.
- visible tutorial text about how to use the deck.
- claims that sound plausible but cannot be traced to source material or explicit assumptions.

Prefer:

- strong first-screen signal: what this is, why it matters, what decision is needed.
- diagrams that explain boundaries and flows, not just component names.
- concise visible text with richer speaker notes.
- explicit tradeoffs, risks, non-goals, and next steps.
- review scorecards that can fail the artifact even when screenshots pass.
