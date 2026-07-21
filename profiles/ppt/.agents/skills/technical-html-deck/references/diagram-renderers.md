# Diagram Renderer Routing

Use this reference after the claim ledger and slide plan are stable. The controller owns semantics; renderers only turn an approved `diagram_spec.json` into visual artifacts.

## Canonical Contract

Each diagram entry must include:

```json
{
  "id": "gateway-runtime",
  "type": "architecture",
  "purpose": "Explain the runtime request path",
  "nodes": [{"id": "ui", "label": "Vibe 页面", "kind": "client"}],
  "edges": [{"source": "ui", "target": "gateway", "label": "HTTPS request", "flow": "sync"}],
  "groups": [],
  "facts": ["claim-ledger:C12"],
  "read_order": ["ui", "gateway"],
  "legend": {"sync": "同步调用"},
  "invariants": ["The browser never calls the internal upstream directly"],
  "style_tokens": {},
  "delivery": {"editable_source": true, "embed_target": "html", "renderer": "auto"},
  "qa": {"no_dangling_edges": true, "no_node_overlap": true, "no_edge_through_node": true, "mobile_legible": true}
}
```

Run `scripts/validate_diagram_spec.py` before invoking a renderer.

## Routing

| Need | Renderer | Canonical delivery |
| --- | --- | --- |
| Simple 3-5 node flow | native HTML/CSS/SVG | HTML/SVG source + screenshot |
| Human-editable architecture, UML, ER, network, sequence | `drawio-skill` | `.drawio` + SVG/PNG |
| C4, cloud deployment, event stream, observability, polished semantic view | `fireworks-tech-graph` | renderer JSON IR + SVG/PNG + validation report |

Use `drawio-skill` when `delivery.editable_source=true` or the user explicitly asks for draw.io. Use `fireworks-tech-graph` when the target is a styled SVG embedded into HTML/PPT and normal users do not need GUI-level component editing.

## Adapter Rules

- Preserve stable node IDs, labels, groups, edge direction, flow type, and claim references.
- Renderer-specific colors, positions, ports, corridors, and waypoints are derived fields.
- If a renderer requires missing semantics, return to the spec or mark the field unknown; do not invent it in the adapter.
- Keep renderer inputs and outputs inside the run folder, for example `diagrams/<id>/spec.json`, `renderer-input.json`, source, export, and QA report.

## QA

Run the renderer's structural validator, then inspect the exported PNG/SVG in the final slide context. The controller still owns these final checks:

- no dangling edge or unexpected node;
- no arrow through nodes, labels, or titles;
- explicit read order and legend when two or more edge types exist;
- precise Chinese labels and numbers match the claim ledger;
- desktop and mobile legibility;
- editable source and embedded export represent the same version.
