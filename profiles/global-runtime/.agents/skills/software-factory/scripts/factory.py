#!/usr/bin/env python3
"""Small, dependency-free state manager for the Codex software factory."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


STAGE_SKILLS = {
    "intake": ["software-factory", "grill-with-docs"],
    "design": ["software-factory", "domain-modeling", "codebase-design"],
    "plan": ["software-factory", "to-spec", "to-tickets"],
    "execute": ["software-factory", "implement", "implement-spec", "tdd"],
    "diagnose": ["software-factory", "diagnosing-bugs", "tdd"],
    "review": ["software-factory", "code-review"],
    "ship": ["software-factory", "pr"]
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def workdir(root: Path, work_id: str) -> Path:
    if not work_id or "/" in work_id or ".." in work_id:
        raise SystemExit("work-id must be a single safe directory name")
    return root / "docs" / "factory" / work_id


def write_once(path: Path, content: str) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}; edit it or choose another work-id")
    path.write_text(content, encoding="utf-8")


def init(args: argparse.Namespace) -> None:
    base = workdir(Path(args.root).resolve(), args.work_id)
    base.mkdir(parents=True, exist_ok=False)
    (base / "receipts").mkdir()
    (base / "briefs").mkdir()
    (base / "inbox").mkdir()
    write_once(base / "intent.md", f"# Intent: {args.work_id}\n\n## Goal\n{args.goal}\n\n## Non-goals\n- TODO\n\n## User decisions\n- TODO\n")
    write_once(base / "spec.md", "# Specification\n\nStatus: draft\n\n## Behavior\n- TODO\n\n## Design decisions\n- TODO\n")
    write_once(base / "plan.md", "# Plan\n\nStatus: draft\n\n## Dependencies\n- TODO\n")
    write_once(base / "decisions.md", "# Decisions\n\nAppend decisions here; do not rewrite prior entries.\n")
    write_once(base / "verify.md", "# Verification\n\n## Commands\n- TODO\n\n## UI/manual checks\n- TODO\n")
    write_once(base / "units.tsv", "id\tstatus\tdepends_on\tscope\tacceptance\tverify\towner\n")
    (base / "ledger.jsonl").touch()
    print(base)


def brief(args: argparse.Namespace) -> None:
    base = workdir(Path(args.root).resolve(), args.work_id)
    if not base.exists():
        raise SystemExit(f"unknown work-id: {args.work_id}")
    path = base / "briefs" / f"{args.unit_id}.md"
    body = f"""# Worker brief: {args.unit_id}\n\nWORK_ID: {args.work_id}\nROLE: {args.role}\nTARGET: {args.target}\n\n## GOAL\n{args.goal}\n\n## BASE\nRead `{base / 'intent.md'}`, `{base / 'spec.md'}`, `{base / 'plan.md'}`, and `{base / 'units.tsv'}` before editing.\n\n## SCOPE\n{args.scope}\n\n## SKILLS\n{args.skills}\n\n## ACCEPTANCE\n{args.acceptance}\n\n## VERIFY\n{args.verify}\n\n## FORBIDDEN\n{args.forbidden}\n\n## TIMEBOX\nOne focused pass. Stop and report if the contract is missing or contradictory.\n\n## REPORT\nWrite a receipt under `receipts/{args.unit_id}.md` with changed files, commands and results, unresolved risks, and the next unit.\n"""
    write_once(path, body)
    append_event(base, {"event": "brief_created", "unit": args.unit_id, "target": args.target})
    print(path)


def add_unit(args: argparse.Namespace) -> None:
    base = workdir(Path(args.root).resolve(), args.work_id)
    if not base.exists():
        raise SystemExit(f"unknown work-id: {args.work_id}")
    units_path = base / "units.tsv"
    with units_path.open(encoding="utf-8", newline="") as fh:
        existing = {row["id"] for row in csv.DictReader(fh, delimiter="\t")}
    if args.unit_id in existing:
        raise SystemExit(f"unit already exists: {args.unit_id}")
    with units_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow([args.unit_id, "ready", args.depends_on, args.scope, args.acceptance, args.verify, args.owner])
    append_event(base, {"event": "unit_added", "unit": args.unit_id, "depends_on": args.depends_on})
    print(units_path)


def append_event(base: Path, event: dict) -> None:
    event = {"at": now(), **event}
    with (base / "ledger.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def record(args: argparse.Namespace) -> None:
    base = workdir(Path(args.root).resolve(), args.work_id)
    if not base.exists():
        raise SystemExit(f"unknown work-id: {args.work_id}")
    append_event(base, {"event": args.event, "unit": args.unit_id, "note": args.note})
    print("recorded")


def status(args: argparse.Namespace) -> None:
    base = workdir(Path(args.root).resolve(), args.work_id)
    units = []
    with (base / "units.tsv").open(encoding="utf-8", newline="") as fh:
        units = list(csv.DictReader(fh, delimiter="\t"))
    events = []
    ledger = base / "ledger.jsonl"
    if ledger.exists():
        events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line]
    print(json.dumps({"work_id": args.work_id, "units": units, "events": events[-20:]}, ensure_ascii=False, indent=2))


def activate(args: argparse.Namespace) -> None:
    skills_repo = Path(args.skills_repo).expanduser().resolve()
    manifest_path = skills_repo / "profiles" / "software-factory" / "software-factory-set.json"
    if not manifest_path.exists():
        raise SystemExit(f"software-factory set not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_name = {entry["name"]: entry for entry in manifest["skills"]}
    packs = manifest.get("packs", {})
    for pack_entries in packs.values():
        for entry in pack_entries:
            by_name.setdefault(entry["name"], entry)
    selected = list(args.skill or [])
    for stage in args.stage or []:
        if stage not in STAGE_SKILLS:
            raise SystemExit(f"unknown stage: {stage}; choose from {', '.join(STAGE_SKILLS)}")
        selected.extend(STAGE_SKILLS[stage])
    for pack in args.pack or []:
        if pack not in packs:
            raise SystemExit(f"unknown pack: {pack}; choose from {', '.join(sorted(packs))}")
        selected.extend(entry["name"] for entry in packs[pack])
    if not selected:
        raise SystemExit("choose --stage or --skill; refusing to activate the whole set implicitly")
    selected = list(dict.fromkeys(selected))
    unknown = [name for name in selected if name not in by_name]
    if unknown:
        raise SystemExit("unknown skill(s): " + ", ".join(unknown))

    target = Path(args.target).expanduser().resolve() / ".agents" / "skills"
    target.mkdir(parents=True, exist_ok=True)
    for name in selected:
        entry = by_name[name]
        source = skills_repo / "profiles" / entry["source_profile"] / ".agents" / "skills" / entry["source_path"]
        destination = target / name
        if destination.exists() and not args.replace:
            raise SystemExit(f"destination exists: {destination}; pass --replace to refresh it")
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
        print(f"activated {name} -> {destination}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=".")
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("init")
    i.add_argument("work_id")
    i.add_argument("--goal", required=True)
    i.set_defaults(func=init)
    b = sub.add_parser("brief")
    b.add_argument("work_id")
    b.add_argument("unit_id")
    b.add_argument("--goal", required=True)
    b.add_argument("--scope", required=True)
    b.add_argument("--acceptance", required=True)
    b.add_argument("--verify", required=True)
    b.add_argument("--forbidden", default="No deploy, merge, schema migration, or dependency upgrade.")
    b.add_argument("--skills", default="implement,tdd")
    b.add_argument("--role", default="implementer")
    b.add_argument("--target", choices=("cloud", "local"), default="cloud")
    b.set_defaults(func=brief)
    u = sub.add_parser("unit")
    u.add_argument("work_id")
    u.add_argument("unit_id")
    u.add_argument("--scope", required=True)
    u.add_argument("--acceptance", required=True)
    u.add_argument("--verify", required=True)
    u.add_argument("--depends-on", default="")
    u.add_argument("--owner", default="unassigned")
    u.set_defaults(func=add_unit)
    r = sub.add_parser("record")
    r.add_argument("work_id")
    r.add_argument("unit_id")
    r.add_argument("event")
    r.add_argument("--note", default="")
    r.set_defaults(func=record)
    s = sub.add_parser("status")
    s.add_argument("work_id")
    s.set_defaults(func=status)
    a = sub.add_parser("activate")
    a.add_argument("--skills-repo", required=True)
    a.add_argument("--target", required=True, help="Project root receiving .agents/skills")
    a.add_argument("--stage", action="append", choices=tuple(STAGE_SKILLS))
    a.add_argument("--pack", action="append")
    a.add_argument("--skill", action="append")
    a.add_argument("--replace", action="store_true")
    a.set_defaults(func=activate)
    return p


if __name__ == "__main__":
    try:
        args = parser().parse_args()
        args.func(args)
    except AttributeError:
        parser().error("a command is required")
