# Linked Project

Use only when the user explicitly wants a same-machine project to follow a local canonical profile by reference. The link is always the profile's entire flat skill directory, never a mixture of individually linked skills:

```text
<project-root>/.agents/skills -> <skills-repo>/profiles/<profile>/.agents/skills
```

The source must be an existing local profile directory. Preflight its resolved
path, direct `SKILL.md` children, and Git status. Then inspect the project path:

- a link resolving to the same source is `linked-current`: no write;
- a link resolving elsewhere is `linked-other`: show both targets and require
  explicit link replacement;
- a physical directory is a migration candidate: compare each direct skill and
  require explicit `migrate-to-link` authorization;
- a missing path can be created after the user explicitly asks to link it.

For a migration, move the existing project `skills` entry to a timestamped
recovery entry immediately under `<project-root>/.agents/`, create the new
`skills` symlink, and verify both the symlink target and readable child
`SKILL.md` files. Do not delete the recovery entry in the same operation. This
leaves a recoverable path for project-specific customizations while removing the
active duplicate from the runtime path.

Linked projects are local development attachments. Do not commit absolute links,
and do not use them for CI, remote machines, or long-lived distributed projects;
use **Project** copy mode from a pushed Git source there.
