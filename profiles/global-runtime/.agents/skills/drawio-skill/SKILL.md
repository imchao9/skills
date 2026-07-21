---
name: drawio-skill
description: Render an approved technical diagram specification into an editable .drawio source and SVG, PNG, PDF, or JPG exports. Use when the user explicitly requests draw.io output, or when technical-html-deck routes a diagram that requires GUI editing, human handoff, or long-term maintenance; do not use as a presentation producer or infer unverified technical relationships.
---

# Draw.io Renderer

Render structure approved by the caller. Do not decide deck narrative, project facts, node membership, or edge semantics.

## Contract

1. Require either a controller-owned `diagram_spec.json` or an explicit user-provided node/edge model.
2. Preserve stable node IDs, labels, groups, edge directions, flow types, facts, read order, legends, and invariants.
3. Treat positions, ports, shapes, styles, corridors, and waypoints as renderer-owned derived fields.
4. If required semantics are absent, return the missing fields instead of inventing them.
5. Deliver editable `.drawio` plus the requested SVG/PNG/PDF/JPG export and validation evidence.

## Workflow

1. Read `references/vendor/upstream-skill.md` for the complete upstream toolbox and prerequisites.
2. Prefer a bundled deterministic generator over hand-written XML.
3. For general node/edge specs, adapt to `scripts/autolayout.py`; use dedicated generators such as `scripts/seqlayout.py` or `scripts/c4.py` when their contract fits.
4. Run `scripts/validate.py` before export.
5. Export with draw.io Desktop when available; if the macOS sandbox blocks it, stop retrying and deliver XML plus the documented browser/non-sandbox fallback.
6. Inspect the exported image. Check overlap, clipping, line crossings, label readability, and agreement with the source spec.

## Boundary

- Do not invoke this renderer merely because a presentation contains three components.
- Do not replace precise diagrams with generated raster images when export fails.
- Do not modify claims to improve layout.
- When called by `technical-html-deck`, keep all artifacts under the deck run folder and return their paths to the controller for final slide-context QA.
