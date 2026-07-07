---
name: technical-html-deck
description: Produce review-ready technical HTML presentations from source docs, existing HTML, markdown, PDFs, screenshots, or architecture material. Use when the user asks for 技术演示稿, HTML 演示稿, PPT-like HTML, technical review deck, architecture presentation, external promo deck, or wants to combine CM style, humanize-ppt structure, html-ppt rendering, and gpt-image2 visual slides.
---

# Technical HTML Deck

Use this skill as the producer layer for technical presentations. It turns source material into a decision-oriented HTML deck, while using other skills as layers:

- `cm-presentation-style`: style gate, scorecard, and CM visual language.
- `humanize-ppt`: narrative structure and speaker logic when available.
- `html-ppt`: static HTML deck rendering when available.
- `gpt-image2-ppt`: visual enhancement branch, not the technical truth layer.
- `technical-deck-qa`: read-only review after generation.

## Workflow

1. Inventory the source.
   - Identify source files, original diagrams, screenshots, source HTML assets, expected audience, and target artifact.
   - Create a run folder under `debug/runs/<date>-<slug>` unless the user gives a destination.
   - Completion: every source and media dependency is listed, including missing or unreadable diagrams.

2. Build the truth layer.
   - Write `claim_ledger.md`: claim, source location, assumption, confidence, challenge risk.
   - Extract architecture, flow, state model, rules, metrics, tradeoffs, risks, non-goals, rollout, and acceptance criteria.
   - Completion: no visible slide claim is unsupported or silently invented.

3. Plan the deck.
   - Read `references/pipeline.md` and `references/layout-bank.md`.
   - Read `references/visual-quality-gate.md` before rendering any serious deck.
   - If `cm-presentation-style` is available, read it and the relevant CM references before visual design.
   - If the user provides a liked or disliked deck, screenshot it and record what to copy, avoid, and verify in `style_brief.md`.
   - Write `slide_plan.json` with page intent, evaluator question, visible points, notes target, diagram/media needs, and layout type.
   - Completion: each page has one job and one evaluation question.

4. Rebuild diagrams.
   - Write `diagram_spec.md` before rendering visual diagrams.
   - Prefer HTML/CSS/SVG or draw.io-style structured diagrams for architecture, sequence, decision, and event models.
   - Use source screenshots only when they are evidence or product UI; do not rely on source HTML diagrams loading by accident.
   - Completion: every referenced diagram has node semantics, edge meaning, read order, legend, and invariants.

5. Choose the rendering branch.
   - Default branch: HTML/CSS deck with editable text and inspectable diagrams.
   - Visual branch: GPT Image or `gpt-image2-ppt` for cover, chapter dividers, external promo visuals, and optional PPTX contact sheets.
   - Read `references/gpt-image2-boundary.md` before using whole-slide image generation.
   - Completion: the branch choice states what remains editable and what must be manually verified.

6. Render and verify.
   - Build a single `deck.html` plus local assets. Keep Chinese-only output unless the source or user explicitly requires English.
   - Run `scripts/check_html_deck.py <deck.html>`.
   - Capture screenshots at desktop and mobile widths; for serious runs, capture every slide or every major section at 1920x1080.
   - Run `scripts/visual_screenshot_check.py <screenshot>` on the first screen and at least one dense page screenshot.
   - Compare screenshots against the visual benchmark notes in `style_brief.md`; revise the HTML before reporting if the deck looks sparse, placeholder-like, or template-generic.
   - Completion: images load, links resolve, text is legible, layouts do not overlap, the first screen carries the subject immediately, and the QA report records residual risk.

7. Report the result.
   - Produce `qa_report.md` with source coverage, rendering checks, style scorecard summary, and unresolved risks.
   - Give the user direct paths to `deck.html`, screenshots, and optional PPTX/contact sheet.
   - Completion: the user can open the artifact and compare it with the source without needing hidden context.

## Required Artifacts

For a serious technical deck run, create:

- `claim_ledger.md`
- `slide_plan.json`
- `diagram_spec.md`
- `style_brief.md`
- `deck.html`
- `qa_report.md`
- screenshots for desktop, mobile, and key dense pages

For quick experiments, at minimum create `deck.html`, one screenshot, and a short notes file explaining skipped gates.

## Default PPT Rule

When the user asks for PPT, HTML PPT, deck, 演示稿, 汇报材料, or PRD presentation output and does not specify another producer, use this skill as the top-level producer.
Do not bypass this skill by directly hand-writing a one-off HTML deck.
Use other PPT skills only as rendering or enhancement branches under this skill, and keep the claim ledger, slide plan, style brief, screenshots, and QA report in the run folder.

## Branch Rules

Internal technical review:

- Optimize for decision quality, not decorative polish.
- Include tradeoffs, risk, non-goals, rollout, and acceptance gates.
- Use diagrams to explain boundaries and flows, not just component names.

External promo HTML:

- Start from the same claim ledger, but rewrite for audience value and proof.
- Use fewer internal details and stronger visual rhythm.
- Never expose private implementation details unless the user explicitly asks.

GPT image / gpt-image2 branch:

- Use it to raise visual finish, not to carry precise technical detail.
- Lock all numbers, product names, system terms, and Chinese copy in the prompt.
- Treat any generated metric, label, or diagram edge as suspect until verified against `claim_ledger.md`.

## Not Done Gates

Do not call the deck done if any of these remain:

- Source architecture diagrams disappeared or were replaced by vague decoration.
- The deck mixes Chinese and English without a deliberate reason.
- A slide contains invented metrics, timelines, system names, or acceptance criteria.
- Technical pages are whole-slide images but the user needs inspectable or editable technical content.
- Screenshots pass but the scorecard would fail the narrative, evidence, or evaluator confidence.
- The first screen looks like an empty slide template, has weak subject signal, or fails to show either a dominant visual, credible diagram, or next-section continuation.
