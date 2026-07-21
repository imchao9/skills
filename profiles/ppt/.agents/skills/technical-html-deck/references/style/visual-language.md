# CM Visual Language

This is the current working style. Treat it as a living system and update after comparing real outputs.

## Shared Traits

- Light base, high contrast, restrained engineering grid.
- One narrow vertical accent bar, not full-page decorative gradients.
- Multi-color accent set: teal, blue, green, amber, rose, slate.
- Cards use 6-8px radius, thin borders, soft shadows only when hierarchy needs it.
- Typography is direct, dense enough for work, never poster-like inside small panels.
- Titles are literal and decision-oriented.
- Visible text is concise; speaker notes carry nuance.

## Color Tokens

- ink: `#0f172a`
- muted: `#475569`
- line: `#d7e0ea`
- surface: `#ffffff`
- canvas: `#f6f9fc`
- teal: `#0f766e`
- blue: `#2563eb`
- green: `#16a34a`
- amber: `#d97706`
- rose: `#e11d48`
- slate: `#64748b`

## Layout Tokens

- Slide/artboard: 16:9, validate at 1920x1080.
- Outer padding: 72-88px for slides.
- Heading: 42-68px depending on role.
- Card body: 18-24px.
- Diagram text: minimum 12px inside SVG, prefer 16-18px for node labels.
- Card radius: 8px or less.
- Diagram frame: full width when diagram is the main evidence; side notes can occupy 300-360px.

## Diagram Rules

- Every diagram must have a visible read order.
- Use lanes for architecture, numbered steps for decision flow, and explicit dashed lines for async/event paths.
- Use labels for edge semantics when ambiguity matters: query, read, write, audit, event, signal.
- Avoid crossing lines unless the crossing has semantic purpose.
- Keep source-document diagrams as raw material, not final visual output.

## Internal vs External

Internal technical review:

- quieter, denser, decision-first.
- diagrams and scorecards are primary.
- avoid marketing language.

External promotional HTML:

- more immersive, stronger object/product signal.
- use screenshots, product visuals, generated images, or interactive scenes.
- copy is shorter and outcome-led.
- CTA is explicit.

## Report-Inspired External Layouts

Use when the target should feel like a credible corporate report or capability update:

- cover: centered or left-aligned giant headline, one colored keyword, rounded visual panels.
- concept page: left thesis, right large model/diagram/proof visual.
- case page: large title, one main image, short evidence columns, optional quote block.
- conclusion: concise statement plus one wide rounded image.

Keep CM identity by using CM colors, real artifacts, and review scorecards; do not imitate another brand's identity.
