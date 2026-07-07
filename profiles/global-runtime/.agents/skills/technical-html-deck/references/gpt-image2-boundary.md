# GPT Image 2 Boundary

Use this reference before applying GPT Image or `gpt-image2-ppt` to a technical deck.

## What It Is Good At

The JuneYaooo `gpt-image2-ppt-skills` approach generates full-slide visual drafts with strong composition, consistent style, and optional PPTX packaging. It is useful for:

- cover pages
- chapter dividers
- external promo visuals
- template style exploration
- contact-sheet comparison
- high-polish pages where exact editability is not required

Repository: https://github.com/JuneYaooo/gpt-image2-ppt-skills

## Boundary

Full-slide image generation is not the technical truth layer.

Treat generated text, numbers, arrows, system names, and timelines as untrusted until checked against `claim_ledger.md`.

Do not use whole-slide image pages as the only version of:

- architecture diagrams that need inspection
- dense rule matrices
- sequence flows with precise edge semantics
- acceptance criteria
- legal, financial, medical, security, or audit evidence

## Recommended Hybrid

Use this split:

```text
HTML/CSS/SVG: source-grounded technical content, diagrams, tables, acceptance gates
GPT Image: hero visuals, atmosphere, chapter pages, external-facing images
PPTX image pack: optional portable artifact or visual comparison output
```

## Prompt Guardrails

When generating image pages:

- state `16:9 landscape widescreen`
- state `all text must be simplified Chinese`
- list exact terms that must not change
- forbid invented numbers and metrics
- keep dense technical diagrams out of the prompt unless they are decorative

After generation:

- compare every visible number and label to `claim_ledger.md`
- reject pages with hallucinated metrics
- regenerate only the visual page, not the source ledger
