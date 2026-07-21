---
name: technical-html-deck
description: Produce review-ready technical HTML presentations from source docs, markdown, PDFs, screenshots, architecture material, or existing decks. Use as the single default producer when the user asks for a technical deck, HTML presentation, PPT-like HTML, architecture review, internal technical review, project retrospective, data report, or external promo presentation; route diagram and output renderers from this skill instead of invoking parallel presentation controllers.
---

# Technical HTML Deck

Use this skill as the only producer/controller for technical presentations. Own the facts, narrative, visual mode, renderer routing, and final QA. Treat diagram, image, HTML, and PPTX skills as execution branches.

## Workflow

1. Inventory the source.
   - Identify sources, diagrams, screenshots, audience, meeting goal, target artifact, and missing evidence.
   - Create `debug/runs/<date>-<slug>` unless the user gives a destination.

2. Build the truth layer.
   - Write `claim_ledger.md`: claim, source, assumption, confidence, challenge risk, and slide.
   - Extract architecture, flows, states, metrics, tradeoffs, risks, non-goals, rollout, and acceptance criteria.
   - Do not allow a renderer to invent nodes, edges, labels, numbers, or conclusions.

3. Plan the deck and style.
   - Read `references/pipeline.md`, `references/layout-bank.md`, and `references/visual-quality-gate.md`.
   - Classify the artifact and read the matching built-in style reference:
     - internal review: `references/style/internal-tech-review.md`;
     - external promo/report: `references/style/external-promo-html.md`;
     - visual tokens: `references/style/visual-language.md`;
     - final review: `references/style/scorecard.md`.
   - Write `style_brief.md` and `slide_plan.json`. Each page must have one job and one evaluator question.

4. Specify and route diagrams.
   - Read `references/diagram-renderers.md`.
   - Write `diagram_spec.json` before rendering any precise technical diagram, then run `scripts/validate_diagram_spec.py diagram_spec.json`.
   - Keep facts and edge semantics in the controller-owned spec. Renderer-specific JSON, XML, or SVG is derived output.
   - Route each diagram independently:
     - simple 3-5 node visual: native HTML/CSS/SVG;
     - editable handoff or long-term maintenance: `drawio-skill`;
     - polished semantic SVG, C4, cloud, event, or reliability view: `fireworks-tech-graph`.

5. Choose output and image branches.
   - Default: HTML/CSS with editable text and inspectable diagrams.
   - Use an HTML or PPTX renderer only after the plan and specs are fixed.
   - Read `references/gpt-image2-boundary.md` before using ImageGen. Use generated images for covers, chapter pages, atmosphere, or visual metaphors; never for precise Chinese labels, numbers, boundaries, or arrows.

6. Render and verify.
   - Build one `deck.html` plus local assets. Default to simplified Chinese.
   - For slide-style output, enforce a `1280x720` logical canvas that scales to `100vw x 100vh`; do not leave a fixed-size card floating inside the viewport.
   - Run `scripts/check_html_deck.py <deck.html>`.
   - Capture every serious slide at 1920x1080 plus mobile and dense-page screenshots.
   - Run `scripts/visual_screenshot_check.py` on the first screen and at least one dense page.
   - Run `scripts/score_deck_static.py` and complete the manual scorecard in `references/style/scorecard.md`.

7. Report the result.
   - Write `qa_report.md` with source coverage, derived-data formulas, renderer checks, diagram validation, style score, screenshot review, and residual risks.
   - Return direct paths to the deck, screenshots, editable diagram sources, and optional PPTX/PDF.

## Required Artifacts

For a serious run, create:

- `claim_ledger.md`
- `slide_plan.json`
- `diagram_spec.json`
- `style_brief.md`
- `deck.html`
- `qa_report.md`
- desktop, mobile, and dense-page screenshots

For a quick experiment, create at least `deck.html`, one screenshot, and notes listing skipped gates.

## Derived Data Contract

For rankings, percentages, durations, or other derived metrics:

- record the source window, inclusion rules, exclusions, formula, and method version;
- never mix cumulative project effort with a weekly activity window in one ranking;
- label estimates and sensitivity ranges explicitly;
- keep the calculation asset next to the deck so the visible chart can be reproduced.

## Renderer Boundaries

- `drawio-skill` and `fireworks-tech-graph` render approved structure; they do not decide technical truth or deck narrative.
- A renderer may reject or surface incomplete semantics, but it must not silently add or reinterpret relationships.
- Renderer failure falls back to another structured renderer or native SVG/HTML, never to ImageGen for a precise diagram.
- Keep editable source (`.drawio` or renderer JSON IR), exported SVG/PNG, and the screenshot actually used by the deck synchronized.

## Not Done Gates

Do not call the deck done when:

- a visible claim is unsupported or a derived number lacks a reproducible formula;
- a technical diagram lacks node semantics, edge meaning, read order, legend, or invariants;
- source architecture disappeared or became vague decoration;
- precise technical content exists only as a generated bitmap;
- the slide canvas does not fill the viewport or clips at desktop/mobile sizes;
- screenshots pass but the narrative, evidence, or style scorecard fails;
- the final deck and audited screenshots reference different assets.
