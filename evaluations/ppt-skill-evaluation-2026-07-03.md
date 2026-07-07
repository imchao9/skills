# PPT Skill Evaluation - 2026-07-03

## Scope

This pass evaluated the additional PPT-related skills provided by the user and installed the reusable candidates into:

```text
/Users/cm/Documents/me/skills/profiles/ppt
```

The profile now exposes 13 skills through `npx skills`.

## Installed Skills

| Skill | Source | Installability | Local status | Fit |
|---|---|---:|---|---|
| `guizang-ppt-skill` | `op7418/guizang-ppt-skill` | Direct `npx skills` | Installed, valid | Strong Chinese HTML deck renderer |
| `codex-ppt` | `ningzimu/codex-ppt-skill` | Direct `npx skills` | Installed, valid | Image-first PPTX generation |
| `ppt-agent` | `sunbigfly/ppt-agent-skills` | Direct `npx skills` | Installed, valid | Full HTML presentation workflow |
| `humanize-ppt` | `LearnPrompt/humanize-ppt` | Direct `npx skills` | Installed, frontmatter normalized | Narrative planning and QA, not a renderer |
| `gorden-ppt-skill` | `GordenSun/GordenPPTSkill` | Direct `npx skills` | Installed, valid | Chinese template-based editable PPTX |
| `cyber-ppt` | `crazyykhllc-bit/CyberPPT` | Not detected from upstream by `npx` | Existing local patched copy kept | Consulting-style editable PPTX |
| `html-ppt` | `lewislulu/html-ppt-skill` | Direct `npx skills` | Installed, valid | Static HTML slide renderer |
| `ian-handdrawn-ppt` | `helloianneo/ian-handdrawn-ppt` | Direct `npx skills` | Installed, valid | Chinese handdrawn technical visuals |
| `image-to-editable-ppt` | `ningzimu/image-to-editable-ppt-skill` | Direct `npx skills` | Installed, valid | Converts existing visual decks to editable PPTX |
| `gpt-image2-ppt` | `JuneYaooo/gpt-image2-ppt-skills` | Direct `npx skills` | Installed, description normalized | Image-model PPT generation |
| `ppt-svg-generator` | `vigorX777/ppt-svg-generator` | Direct `npx skills` | Installed, frontmatter normalized | Markdown to PPT-importable SVG pages |

## Security Notes From `npx skills`

| Skill | Registry risk note |
|---|---|
| `guizang-ppt-skill` | Safe / Low Risk |
| `codex-ppt` | Safe / Low Risk |
| `ppt-agent` | Safe / Med Risk |
| `humanize-ppt` | Safe / Critical Risk, 2 socket alerts |
| `gorden-ppt-skill` | High Risk / Critical Risk |
| `html-ppt` | Safe / Low Risk |
| `ian-handdrawn-ppt` | Safe / Low Risk |
| `image-to-editable-ppt` | Safe / Med Risk |
| `gpt-image2-ppt` | Safe / Med Risk |
| `ppt-svg-generator` | Safe / Med Risk, 1 socket alert |

Treat Critical/High risk skills as research candidates until their scripts and dependency paths are reviewed.

## Current Recommendation

For the login-risk technical方案材料 already tested in the debug bench:

1. `cyber-ppt` remains the best default for technical方案评审 because its consulting-style structure surfaces decision logic, gates, and evidence.
2. `ppt-master` remains the safest editable fallback.
3. Add `gorden-ppt-skill`, `guizang-ppt-skill`, and `html-ppt` to the next rendering benchmark.
4. Use `humanize-ppt` as a pre/post processor around HTML renderers rather than comparing it as a standalone output.
5. Use `image-to-editable-ppt` only after another skill has produced PNG/PDF slides.

## Verification

Commands run:

```bash
env -u http_proxy -u https_proxy -u all_proxy npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/ppt --list --full-depth
```

Result: `npx skills` found 13 skills.

Strict local validation passed after normalizing frontmatter:

```bash
/Users/cm/Documents/me/skill_check/.venv-skill-eval/bin/python /Users/cm/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-dir>
```
