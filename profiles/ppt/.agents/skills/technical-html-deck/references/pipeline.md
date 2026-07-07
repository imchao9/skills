# Pipeline

Use this reference when turning technical source material into an HTML presentation.

## Source Pass

Collect:

- primary source files and their paths
- embedded assets and diagrams
- source claims that should survive into slides
- evaluator questions the deck must answer
- known objections, especially cost, scope, maintainability, and rollout risk

Create `claim_ledger.md` before writing final slide copy. Keep it short but traceable.

Recommended columns:

```text
claim | source | assumption | confidence | challenge risk | slide
```

## Structure Pass

Create `slide_plan.json` before rendering.

Recommended fields:

```json
{
  "slide": 1,
  "layout": "decision-cover",
  "title": "方案评审",
  "evaluator_question": "这次会议需要决定什么？",
  "visible_points": [],
  "speaker_notes_target": "",
  "diagram_need": "",
  "source_claims": []
}
```

The visible slide should be concise; speaker notes or `notes.md` can carry fuller technical explanation.

## Rendering Pass

Default to static HTML when the deck needs:

- editable Chinese text
- inspectable architecture diagrams
- reusable visual profile
- browser screenshots for QA
- future conversion to PDF or PPTX images

Use full-slide image generation only when the page is a visual statement, not the canonical technical record.

## Verification Pass

Minimum checks:

- `scripts/check_html_deck.py <deck.html>`
- desktop screenshot
- mobile screenshot
- key dense slide screenshot
- manual visual check for overlap, missing assets, and diagram legibility

Serious technical review checks:

- every slide screenshot at 1920x1080
- claim ledger matches visible claims
- diagram spec matches rendered diagrams
- `qa_report.md` lists blockers, fixes, and residual risk
