#!/usr/bin/env python3
"""Refresh the composed software-factory profile from local source profiles."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def manifest_entries(manifest: dict) -> list[dict]:
    entries = list(manifest.get("skills", []))
    for pack_entries in manifest.get("packs", {}).values():
        entries.extend(pack_entries)

    by_name: dict[str, dict] = {}
    for entry in entries:
        name = entry.get("name")
        source_profile = entry.get("source_profile")
        source_path = entry.get("source_path")
        if not all(isinstance(value, str) and value for value in (name, source_profile, source_path)):
            raise SystemExit(f"invalid manifest entry: {entry!r}")
        if Path(name).name != name or Path(source_profile).is_absolute() or Path(source_path).is_absolute():
            raise SystemExit(f"manifest paths must be relative and skill names flat: {entry!r}")
        if ".." in Path(source_profile).parts or ".." in Path(source_path).parts:
            raise SystemExit(f"manifest paths may not contain '..': {entry!r}")

        previous = by_name.get(name)
        if previous is not None:
            previous_source = (previous["source_profile"], previous["source_path"])
            current_source = (source_profile, source_path)
            if previous_source != current_source:
                raise SystemExit(
                    f"skill {name!r} has conflicting sources: "
                    f"{previous_source!r} and {current_source!r}"
                )
            continue
        by_name[name] = entry
    return list(by_name.values())


def remove_target(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Skills repository root")
    parser.add_argument(
        "--mode",
        choices=("copy", "symlink"),
        default="copy",
        help="Materialize files for publishing, or link source skills for local co-development",
    )
    parser.add_argument(
        "--destination",
        help="Override the generated .agents/skills directory (useful for isolated checks)",
    )
    parser.add_argument("--check", action="store_true", help="Only validate sources")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    manifest_path = repo / "profiles" / "software-factory" / "software-factory-set.json"
    if not manifest_path.exists():
        raise SystemExit(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    destination = (
        Path(args.destination).expanduser().resolve()
        if args.destination
        else repo / "profiles" / "software-factory" / ".agents" / "skills"
    )
    entries = manifest_entries(manifest)
    missing = []
    for entry in entries:
        source = repo / "profiles" / entry["source_profile"] / ".agents" / "skills" / entry["source_path"]
        if not (source / "SKILL.md").exists():
            missing.append(str(source))
    if missing:
        raise SystemExit("missing source skills:\n" + "\n".join(missing))
    if args.check:
        print(
            f"validated {len(entries)} source skills across "
            f"{len(manifest.get('packs', {}))} packs (mode={args.mode})"
        )
        return

    destination.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        source = repo / "profiles" / entry["source_profile"] / ".agents" / "skills" / entry["source_path"]
        target = destination / entry["name"]
        remove_target(target)
        if args.mode == "symlink":
            relative_source = os.path.relpath(source, target.parent)
            target.symlink_to(relative_source, target_is_directory=True)
            print(f"linked {entry['name']} -> {relative_source}")
        else:
            shutil.copytree(source, target)
            print(f"copied {entry['name']} <= {source}")


if __name__ == "__main__":
    main()
