---
name: fireworks-tech-graph
description: Render an approved technical diagram specification into geometry-checked semantic SVG, PNG, offline HTML, or an explicitly requested validated GIF. Use when the user explicitly asks for Fireworks output, or when technical-html-deck routes a polished C4, cloud deployment, event-stream, observability, reliability, agent, or memory diagram; do not use as a presentation producer or invent technical facts.
---

# Fireworks Semantic SVG Renderer

Render controller-approved semantics into a polished, testable visual. The renderer JSON IR is the editable source of truth for this branch; the exported SVG is derived output.

Resolve the skill root before commands:

```bash
SKILL_ROOT="${CLAUDE_SKILL_DIR:-/absolute/path/from-codex-skill-metadata}"
```

## Contract

1. Require a controller-owned `diagram_spec.json` or explicit user-provided structure.
2. Preserve node IDs, labels, groups, edge direction, flow type, facts, read order, legends, and invariants.
3. Treat geometry, ports, corridors, route points, style choice, and motion timing as renderer-owned derived fields.
4. Return missing or contradictory engineering facts to the caller; do not repair them by invention.
5. Deliver renderer JSON IR, SVG, requested export, layout/validation report, and visual-review status.

## Workflow

1. Read `references/vendor/upstream-skill.md` for full upstream commands, semantic profiles, styles, and dependency boundaries.
2. Adapt the approved spec into the nearest versioned schema under `schemas/`.
3. Run `scripts/fireworks.py validate` before layout when the selected semantic profile supports it.
4. Render through `scripts/fireworks.py` or `scripts/generate-from-template.py`.
5. Run `scripts/fireworks.py check` or `scripts/validate-svg.sh`.
6. Export PNG and visually inspect the final diagram. Allow at most two focused geometry corrections.
7. Generate GIF only when the user explicitly requests motion with language such as `让这张图动起来`, `生成 GIF`, `制作 GIF`, `Animate this diagram`, or `Generate a GIF`; keep motion dependencies out of the normal deck path. Styles 1–12 are enabled under the upstream motion contracts, including the `+2s-settled-flow` timing revision.

## Boundary

- Do not trigger for a generic presentation request; `technical-html-deck` owns that entry.
- Do not equate SVG editability with draw.io-style GUI editing. Stable changes should modify JSON IR and re-render.
- Do not use the AI-authored/static style as the production default when deterministic replay is required.
- When called by `technical-html-deck`, keep all artifacts under the deck run folder and return them to the controller for final slide-context QA.
