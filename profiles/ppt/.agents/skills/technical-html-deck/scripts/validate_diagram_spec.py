#!/usr/bin/env python3
"""Validate the controller-owned diagram_spec.json without third-party packages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED = {"id", "type", "purpose", "nodes", "edges", "facts", "read_order", "invariants", "delivery", "qa"}


def validate_diagram(item: object, index: int) -> list[str]:
    prefix = f"diagram[{index}]"
    if not isinstance(item, dict):
        return [f"{prefix} must be an object"]
    errors = [f"{prefix} missing {key}" for key in sorted(REQUIRED - item.keys())]
    nodes = item.get("nodes", [])
    edges = item.get("edges", [])
    if not isinstance(nodes, list) or not nodes:
        errors.append(f"{prefix}.nodes must be a non-empty list")
        nodes = []
    if not isinstance(edges, list):
        errors.append(f"{prefix}.edges must be a list")
        edges = []
    node_ids: list[str] = []
    for node_index, node in enumerate(nodes):
        if not isinstance(node, dict) or not node.get("id") or not node.get("label"):
            errors.append(f"{prefix}.nodes[{node_index}] requires id and label")
            continue
        node_ids.append(str(node["id"]))
    if len(node_ids) != len(set(node_ids)):
        errors.append(f"{prefix}.nodes contains duplicate ids")
    known = set(node_ids)
    for edge_index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"{prefix}.edges[{edge_index}] must be an object")
            continue
        source, target = edge.get("source"), edge.get("target")
        if source not in known or target not in known:
            errors.append(f"{prefix}.edges[{edge_index}] has unknown endpoint {source!r}->{target!r}")
        if not edge.get("label") or not edge.get("flow"):
            errors.append(f"{prefix}.edges[{edge_index}] requires label and flow")
    read_order = item.get("read_order")
    if not isinstance(read_order, list) or not read_order:
        errors.append(f"{prefix}.read_order must be a non-empty list")
    elif unknown := [node_id for node_id in read_order if node_id not in known]:
        errors.append(f"{prefix}.read_order has unknown nodes: {unknown}")
    for key in ("facts", "invariants"):
        if not isinstance(item.get(key), list) or not item.get(key):
            errors.append(f"{prefix}.{key} must be a non-empty list")
    delivery = item.get("delivery")
    if not isinstance(delivery, dict) or delivery.get("renderer") not in {"auto", "native", "drawio", "fireworks"}:
        errors.append(f"{prefix}.delivery.renderer must be auto, native, drawio, or fireworks")
    if not isinstance(item.get("qa"), dict):
        errors.append(f"{prefix}.qa must be an object")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a technical-html-deck diagram spec.")
    parser.add_argument("spec", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}")
        return 2
    diagrams = data.get("diagrams") if isinstance(data, dict) else None
    if diagrams is None and isinstance(data, dict):
        diagrams = [data]
    if not isinstance(diagrams, list) or not diagrams:
        print("FAIL expected one diagram object or an object with a non-empty diagrams list")
        return 1
    errors = [error for index, item in enumerate(diagrams) for error in validate_diagram(item, index)]
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(f"PASS {len(diagrams)} diagram spec(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
