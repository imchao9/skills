---
name: install-profile-skills
description: Install or link one or more Skill profiles into explicit project roots, custom flat skill directories, the managed global-runtime profile, or Codex global skills. Use when the user asks to map profiles to projects, install copied skills, make a same-machine project follow a canonical profile by reference, migrate duplicate project skills, upgrade an old project skill directory, or preview collisions. Route through existing Vercel skills CLI and filesystem primitives; do not create another package manager, manifest, or source registry.
x-provenance: local
x-owner: cm
x-source-note: created to route profile installs to explicit project, custom, and global destinations
---

# Install Profile Skills

Install profile contents into exact destinations while preserving profile provenance, existing target files, and global-runtime governance. Use existing installers and filesystem primitives; do not build a new installer CLI or script.

## Collect the Install Map

Represent the request as one or more rows:

| Source | Selector | Destination mode | Destination |
| --- | --- | --- | --- |
| profile path or Git source | `*` or exact skill names | project, linked-project, custom-flat, global-runtime, codex-global | absolute project root or skill directory |

Infer values already explicit in the request or repository. Ask one concise question only when source, target, or global meaning cannot be determined safely.

## Preflight Every Row

Perform these checks without writing:

1. Resolve the source to a local profile path or a pushed Git source.
2. Enumerate only direct child directories containing `SKILL.md`; ignore caches, outputs, locks, and type directories.
3. Resolve the exact destination using [destination-modes.md](references/destination-modes.md). Inspect symlinks before selecting a physical target; for a linked project, resolve both the current link and the requested canonical profile.
4. Inspect the target Git root and working tree when present. Preserve all existing changes.
5. Compare source skill names with the destination and classify each as `new`, `identical`, `different`, or `unknown`.
6. Show a dry-run summary containing source, resolved physical destination, selected skills, collisions, planned command, and files that may change.

Dry-run is the default when the user asks to preview, plan, map, or check. Execute immediately only when the user explicitly asks to install or copy and the exact source and destination are resolved.

## Choose the Source

- Use `imchao9/skills/profiles/<profile>` for long-lived projects only after the relevant profile changes are committed and pushed.
- Use the local profile path for validating current unpushed changes on the same machine.
- Use another GitHub repository/path only when the user names it; delegate network installation to the system `skill-installer` workflow.
- Never present an unpushed local profile as installable from Git source.

## Execute by Destination Mode

Read [destination-modes.md](references/destination-modes.md) before executing.

- **project**: run Vercel `skills@latest add` from the target project root with `--copy --full-depth`; let the project own `.agents/skills` and its lock.
- **linked-project**: use a local canonical profile only and link the exact `<project>/.agents/skills` path to that profile's `.agents/skills` directory. This is for same-machine co-development where the project should immediately follow canonical skill upgrades. Read [linked-project.md](references/linked-project.md) before changing anything.
- **custom-flat**: install selected skills into the exact flat skill directory. Use the system skill-installer `--dest` path for GitHub sources. For local sources, copy only selected skill directories after collision checks.
- **global-runtime**: modify the canonical `profiles/global-runtime/.agents/skills`, never the `~/.agents/skills` symlink. Read `profiles/global-runtime/UPSTREAM.md`, require explicit selected skill names, and refuse blind whole-profile promotion.
- **codex-global**: target the resolved Codex global skills directory, normally `<codex-home>/skills`. Treat this as Codex-only installation, distinct from the managed cross-agent global runtime.

For a multi-row install map, complete preflight for all rows first, then execute rows sequentially. Stop before the first unresolved collision; do not partially overwrite a later target.

## Collision Contract

- `new`: install normally.
- `identical`: skip and report it.
- `different`: show a concise diff summary and require explicit authorization for the exact skill before replacement.
- `unknown`: stop and resolve readability, symlink, or source issues.

For **linked-project**, classify the directory itself: `linked-current`,
`linked-other`, `physical-identical`, `physical-different`, or `missing`.
Only `linked-current` is already deduplicated. A `physical-*` directory is a
migration, not a silent replacement: preserve it under `.agents/` with a
timestamped recovery name before creating the new link, then verify the link.

Never delete, replace, merge, or move an existing destination directory merely because `--yes` is available. If replacement is authorized, preserve a recoverable backup when the installer itself does not provide one.

## Global Guardrails

- Do not edit `~/.agents/skills` directly when it is a symlink.
- Do not bulk-copy a source profile into `global-runtime`; promotion is per skill and follows `UPSTREAM.md`.
- Do not copy Codex plugin-provided skills into profile directories.
- Do not install `.system` skills separately.
- Do not commit, push, or update unrelated profile locks unless the user explicitly requests it.
- Do not create a new manifest or source registry; use the repository profile structure, Git history, existing lock files, and `UPSTREAM.md`.

## Verify the Installed Result

After each executed row:

1. Confirm every selected destination contains a readable `SKILL.md`.
2. For local copies, compare source and destination bytes or run a recursive diff. For linked projects, resolve `readlink`/`realpath` and confirm it equals the requested canonical profile directory.
3. For project mode, run the available skills listing command and confirm the selected names are discoverable. For linked projects, confirm the canonical direct child skill names are visible through the project link.
4. Re-check target Git status and report only paths changed by this installation.
5. Report source, physical destination, installed/skipped/conflicted names, verification evidence, and whether a new task or runtime refresh is needed.

Installation success means verified files at the resolved destination, not merely a zero exit code from an installer.
