# Design-to-Code Checklist

Use this reference when implementing from Figma, Paper, screenshots, prototypes, or another visual source.

## Establish authority

Identify the authoritative frame, page, component state, viewport, and source revision.
Prefer structured design data over screenshot inference when both are available.
List missing information such as breakpoints, interaction states, real content, icons, fonts, tokens, animation, and accessibility behavior.
Do not silently invent missing product behavior.

## Map design to the codebase

Inspect the existing component library, tokens, typography, spacing, icons, assets, routing, and layout primitives.
Create a mapping before implementation:

| Design node | Existing component or new component | Token or style source | States | Responsive rule | Open question |
| --- | --- | --- | --- | --- | --- |

Reuse an existing component when its semantics and supported states match.
Do not reuse a visually similar component when doing so breaks its contract.
Create a new component only when it represents a stable responsibility or repeated pattern.

## Extract visual rules

Capture:

- Typography family, size, weight, line height, and truncation.
- Color roles rather than isolated hex values.
- Spacing rhythm, alignment, container widths, and grids.
- Border, radius, shadow, opacity, and elevation.
- Icons, images, aspect ratios, crops, and empty assets.
- Auto-layout or constraint signals that imply responsive behavior.

Map values to repository tokens when a close authoritative token exists.
Record deliberate exceptions instead of creating near-duplicate tokens.

## Model interaction states

Identify default, hover, active, focus, disabled, loading, empty, error, selected, expanded, and destructive states as relevant.
Define keyboard behavior and focus movement for dialogs, menus, tabs, forms, and composite widgets.
Do not treat a static frame as evidence that these states are unnecessary.

## Implement in stages

1. Build semantic structure and responsive layout.
2. Apply tokens and reusable components.
3. Connect representative data and all relevant states.
4. Add interactions and transitions.
5. Integrate the real data contract.
6. Refine visual differences after browser comparison.

Avoid generating one large component with duplicated inline styles.
Avoid absolute positioning for normal document layout unless the design truly requires layered composition.

## Compare visually

Render at the authoritative viewport and every required breakpoint.
Compare screenshot evidence for geometry, typography, spacing, color, assets, and state.
Then inspect nearby widths to expose brittle breakpoint behavior.

Record mismatches as measurable observations such as offset, size, wrapping, clipping, or token difference.
Fix the underlying layout or token rule rather than adding unrelated pixel nudges.

Do not claim faithful design reproduction until the rendered interface has been compared with the authoritative source.
