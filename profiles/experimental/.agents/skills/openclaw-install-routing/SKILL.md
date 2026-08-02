---
name: openclaw-install-routing
description: Choose and execute the safest OpenClaw/Codex installation authentication route between direct MatrixRouter API keys and centralized Codex Auth Sync/CLIProxy, including model-version discovery and tar.zst bootstrap checks. Use when provisioning a Mac, changing Codex or OpenClaw credentials, deciding whether to use MatrixRouter or Auth Sync, diagnosing enrollment or approval issues, or preventing zstd decompression delays.
x-provenance: local-candidate
x-owner: cm
x-source-note: local installation-routing skill; original creation context not fully confirmed
---

# OpenClaw Install Routing

Use direct MatrixRouter as the default route for a new Mac when an individual OpenAI-compatible key is available and OpenClaw should use Anthropic Claude through MatrixRouter. Use Auth Sync only when the machine must consume a centrally managed CLIProxy/Codex account and a valid one-time enrollment code plus administrator approval are available.

Do not put secrets in commands, reports, plans, or files outside the target's protected configuration. Keep every credential file at mode `0600`.

## Start with guided intake

Do not start installation on the first request. First explain that no secret is needed yet, then collect the four short answers below. Ask one question at a time if the user prefers conversation; otherwise run the local collector.

1. **Target:** `M26A`, `M15A`, `M15I`, or `M14I`.
2. **Network:** `VPN` to install and restore Clash Party, or `DIRECT`.
3. **Authentication:** `MR` for MatrixRouter direct, or `SYNC` for centralized Codex Auth Sync.
4. **Scope:** `LITE`, `CORE`, or `FULL`.

Then ask only the route-specific readiness question:

- `MR`: whether the MatrixRouter OpenAI-compatible key is available; if OpenClaw is selected, whether the MatrixRouter Anthropic key is available.
- `SYNC`: whether a valid enrollment code is available and whether the administrator has approved the device.

Never request the key or enrollment-code value during intake. Ask for the value only after the plan is accepted and protected execution begins.

When the installer repository checkout is available, prefer its guided planner. It asks the four answers and prints a profile-specific assessment command without contacting a target or accepting secrets:

```bash
bash /path/to/openclaw-installer/scripts/install-wizard.sh
```

For a non-interactive handoff, pass an install card and credential-presence flags only:

```bash
bash /path/to/openclaw-installer/scripts/install-wizard.sh \
  --card M26A-VPN-MR-CORE \
  --matrixrouter-openai present \
  --matrixrouter-anthropic present
```

Review and complete the generated `assess` command before explicitly running any `apply` command.

For a trusted colleague who should execute the full installation independently, use the repository-owned delegated entry point instead. It creates a temporary `0600` inventory from `USER@HOST`, prompts for passwords locally, runs assessment, and requires them to type `APPLY` before changing the target:

```bash
bash /path/to/openclaw-installer/scripts/delegated-install.sh \
  --host mac@10.240.33.205 \
  --card M26A-VPN-MR-CORE \
  --matrixrouter-openai present \
  --matrixrouter-anthropic present
```

The colleague needs access to the approved private installer checkout and only the secrets required for that installation. Do not distribute a personal long-lived credential bundle when a per-run or per-machine package can be used.

When the colleague should install from their own Mac without receiving the full repository, build the HTTP operator bundle. It excludes `upload-packages/` and `.package-build/`; the package URL is requested at runtime when omitted:

```bash
bash scripts/build-delegated-installer-bundle.sh \
  --output /secure-transfer/openclaw-delegated-installer.tar.gz
```

The archive contains private configuration. Confirm the private-secret scope first, transfer it only through an approved secure channel, and provide a reachable package HTTP endpoint before installation.

Use the collector only when the repository checkout is unavailable:

```bash
python3 scripts/collect_install_brief.py
```

## Fast install cards

Accept a four-part install card: `<target>-<network>-<auth>-<scope>`.

| Position | Codes | Meaning |
|---|---|---|
| Target | `M26A`, `M15A`, `M15I`, `M14I` | macOS 26 arm64, macOS 15 arm64, macOS 15 Intel, macOS 14 Intel |
| Network | `VPN`, `DIRECT` | Restore Clash Party or do not install/restore it |
| Auth | `MR`, `SYNC` | MatrixRouter direct or Codex Auth Sync/CLIProxy |
| Scope | `LITE`, `CORE`, `FULL` | Minimal, main workflow, or include deferred extras and Office skills |

Examples:

```text
M26A-VPN-MR-CORE
M14I-DIRECT-SYNC-LITE
```

The card never includes a key, token, password, or enrollment code. After receiving a card, ask only for the credential *presence* needed to prove the route is feasible; obtain actual secrets only at the protected execution step.

## Decide before changing configuration

Run the planner with presence flags only; it never accepts key values:

```bash
python3 scripts/plan_route.py --mode auto \
  --matrixrouter-openai present --matrixrouter-anthropic present \
  --auth-sync-code absent --need-openclaw
```

Or expand an install card directly:

```bash
python3 scripts/plan_route.py --preset M26A-VPN-MR-CORE \
  --matrixrouter-openai present --matrixrouter-anthropic present
```

Use its route unless the user explicitly changes the requirement.

For a repeatable installation, copy `references/install-spec.example.json` to a private run directory, select components with booleans, then generate the plan:

```bash
python3 scripts/plan_route.py --spec /private/run/install-spec.json
```

The spec contains only route, component, model, and credential-presence metadata. Do not put an API key, enrollment code, or token in it.

For an interactive request, collect exactly these four answers first: target code, network code, auth code, and scope code. Generate the preset plan, report blockers, then ask only for the secret required by the selected route.

| Requirement | Route |
|---|---|
| Codex + OpenClaw Claude on a new Mac; MatrixRouter OpenAI and Anthropic keys available | `matrixrouter` |
| Central shared Codex/CLIProxy account; one-time code and admin approval available | `auth-sync` |
| Central Codex account but OpenClaw must use MatrixRouter Claude | `split` only after checking configuration writers; never run a writer that overwrites both apps |
| Auth Sync code expired, not approved, or no admin | `matrixrouter` if keys exist; otherwise stop |

Auth Sync manages CLIProxy authentication. It does not supply a MatrixRouter Anthropic key and must not be presented as an OpenClaw-Claude setup path.

## Apply the selected route

### MatrixRouter

1. Query the authenticated `/v1/models` endpoint before writing configuration. Select IDs from that response; do not guess word order. The currently validated Codex ID was `gpt-5.6-sol`, not `gpt-sol-5.6`.
2. Run `configure-matrixrouter.py --targets codex,openclaw --validate-models`. This rejects an unavailable model before writing either config and leaves Claude Code settings untouched by default.
3. Configure OpenClaw separately with `api: anthropic-messages` and its selected Claude model. Keep any intended fallback explicit.
4. Restart the gateway and run one minimal Codex and OpenClaw `HELLO_OK` probe.

Use the installer repository's `scripts/configure-matrixrouter.py` only after confirming whether its scope includes Claude Code settings; if the request is only Codex and OpenClaw, preserve unrelated settings.

### Auth Sync

1. Use the v2 architecture-aware installer only, with HTTPS and SHA-256 verification.
2. Pass the enrollment code through stdin, a `0600` file, or an interactive prompt; never a command-line argument.
3. Verify registered state, obtain administrator approval, then perform the first safe sync. Require explicit approval before a forced replacement of a local auth file.
4. Point Codex/OpenClaw at CLIProxy only when that is the selected route. Do not overwrite an existing direct MatrixRouter configuration accidentally.

Read the existing `install-codex-auth-sync` skill for installer and approval mechanics.

## Version policy

- Use the package's tested Codex CLI version unless a live smoke test fails; record `codex --version` in the acceptance report.
- Treat model IDs as account-scoped runtime data. Query `/v1/models` using the supplied key and smoke-test the selected model.
- Pin the Auth Sync installer digest, not merely its URL. Record its Agent status/version without outputting tokens.
- Keep OpenClaw's model and API adapter paired: Claude through MatrixRouter requires `anthropic-messages`; do not substitute an OpenAI adapter merely because Codex uses Responses.

## tar.zst preflight

Before downloading multi-gigabyte archives, run `scripts/check_zstd.sh` on the target. The packaged fetcher also performs this check before transfer. If it fails, choose one of these in order:

1. Use a bundled, checksummed architecture-specific bootstrap zstd tool delivered as a small `.tar.gz` archive.
2. Use the target's native tar only if it can successfully list a representative `.tar.zst` archive.
3. Install `zstd` through Homebrew only as an explicit fallback; set `INSTALL_ZSTD_IF_MISSING=1` to start that explicit fallback in parallel with package download.

Do not make Homebrew installation an implicit mid-extraction surprise. Read `references/zstd-bootstrap.md` before changing package distribution.

## Parallelism rules

Use the plan's `waves` output. Parallelize only package transfer and zstd readiness. Keep extraction, package verification, `/Applications` changes, global npm changes, configuration writes, gateway restart, and smoke tests serial.

Defer optional extras and Office skills until the core validation succeeds. This shortens time-to-first-usable-install without creating shared-state races.

Read `reports/install-phase-timing.jsonl` after every run. It records each selected phase's `pass`/`fail` result and duration, so the next optimization is based on actual phase cost rather than terminal history.
