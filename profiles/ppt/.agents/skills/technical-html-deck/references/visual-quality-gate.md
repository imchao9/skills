# Visual Quality Gate

Use this reference before rendering serious HTML decks and again during QA.
The goal is to prevent ugly-but-valid decks: pages that render, but look sparse, generic, or unfinished.

## Benchmark Pass

If the user provides a reference deck, screenshot it before editing.
Record these fields in `style_brief.md`:

```text
benchmark path:
liked traits:
traits to avoid:
first-screen contract:
layout mode:
color and typography notes:
QA screenshots:
```

If no reference is provided, use the closest local exemplar before inventing a new style.
Current local exemplar for report-style technical HTML:

```text
/Users/cm/Documents/Me/Playground/Improve/docs/technical-presentation-generation-summary.html
```

Treat local exemplars as visual calibration, not as content templates.
Copy structure and quality bar; do not copy claims, product wording, or private facts.

## First-Screen Contract

The first 1080px of a report-style or PPT-like HTML deck must show:

- a clear subject signal in the title or hero area.
- the decision, report, or presentation purpose.
- one dominant visual: concept map, system diagram, product screenshot, table, or evidence panel.
- enough surrounding content to avoid looking like an empty title slide.
- a hint of the next section on desktop when the format is scroll-based.

The first screen fails if it is mostly whitespace, generic title text, three loose cards, or decorative shapes without technical meaning.

## Layout Selection

Use report-style vertical HTML when the user wants a PRD, technical plan, audit report, or decision document that will be read and shared.
Use slide-style horizontal HTML when the user explicitly asks for stage presentation, page-by-page delivery, or projector-first format.
Use PPTX only when editable PowerPoint output is required.

For report-style technical HTML, prefer:

- sticky top navigation.
- hero with thesis plus system visual.
- white paper sections on a light technical canvas.
- dense but readable cards, tables, and diagrams.
- visible continuation from one section to the next.

For slide-style technical HTML, prefer:

- one claim per slide.
- one dominant evidence visual per slide.
- appendix pages for dense details.
- screenshots for every slide.

## Fullscreen Contract

Use a `1280x720` logical slide canvas and scale the active slide uniformly into `100vw x 100vh`. Do not present a fixed-size slide as a floating card with unused viewport margins. Preserve aspect ratio with letterboxing only when the viewport is not 16:9; mobile may switch to natural-height scrolling when explicitly designed and verified.

Test at least:

- 1920x1080 desktop;
- 1280x720 desktop;
- one narrow mobile viewport;
- browser zoom or device-pixel-ratio conditions that previously caused clipping.

## Anti-Ugly Checks

Before calling the deck done, inspect screenshots and fix any of these:

- first screen feels like a placeholder or wireframe.
- hero/title area is oversized relative to content.
- repeated card grids make the deck look auto-generated.
- diagrams use component names but no edge semantics.
- color palette is dominated by one hue without functional accents.
- text is too tiny, too loose, clipped, or awkwardly wrapped.
- screenshots prove the page renders but not that it is presentation-worthy.
- chart bar lengths, sort order, labels, denominators, or time windows imply a comparison the data does not support.
- the final HTML references assets different from the files used during screenshot QA.

## QA Report Requirements

`qa_report.md` must state:

- which benchmark or reference style was used.
- screenshot files checked.
- visual issues found and fixed.
- remaining visual risk, if any.
- whether `visual_screenshot_check.py` passed for first screen and dense page screenshots.
