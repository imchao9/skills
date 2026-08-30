# Destination Modes

## Project

Use when the user names a project root and wants that project to own copied skills.

Resolved destination:

```text
<project-root>/.agents/skills
```

Run from `<project-root>`:

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add <source-profile> \
  --agent codex --skill '<selector>' --yes --copy --full-depth
```

Use `*` only when the user requested the whole profile. Prefer exact names for partial installs. Git source is preferred for committed, pushed, long-lived use; a local profile path is for same-machine validation of unpushed changes.

For a project that should follow one local canonical profile by reference rather
than own copies, use [Linked Project](linked-project.md) instead.

## Custom Flat Directory

Use when the destination itself must contain:

```text
<destination>/<skill-name>/SKILL.md
```

For GitHub skill paths, use the system `skill-installer` helper with its `--dest <destination>` option. For a local profile, enumerate selected direct skill children, compare collisions, then copy only new or explicitly authorized names.

Reject broad targets such as `/`, a home directory, or an unresolved variable. Create only the exact destination after resolving it to an absolute path.

## Managed Global Runtime

Use when the user means cross-agent global skills managed by the personal profile repository.

Resolve the repository root and use:

```text
profiles/global-runtime/.agents/skills
```

Do not write through `~/.agents/skills` even when it points there. Read `profiles/global-runtime/UPSTREAM.md`, identify the canonical source policy, and promote explicit skill names only. Add or update source governance when the selected skill has no recorded canonical source.

Whole-profile `*` promotion is not a normal operation. If explicitly requested, show the complete collision and source-policy report and require confirmation before any write.

## Codex Global

Use when the user explicitly means Codex-only global skills.

Resolved destination:

```text
<codex-home>/skills
```

Do not assume this is the same as `~/.agents/skills`. Resolve the active Codex home from the environment or current installation. Use the system `skill-installer` for GitHub paths. For local skills, apply the same exact-name collision and byte-verification contract as custom-flat mode.

Tell the user that newly installed Codex skills are most reliably discovered on the next task when the current runtime does not refresh its catalog immediately.

## Batch Mapping Example

```text
core -> /work/project-a (project, all skills)
ppt -> /work/project-b (project, selected skills)
web -> /work/project-c/.agents/skills (custom-flat, agent-reach)
core/draft-internal-requirement-brief -> Codex global (codex-global)
```

Preflight all four rows first. Execute sequentially only after every path and collision is resolved.
