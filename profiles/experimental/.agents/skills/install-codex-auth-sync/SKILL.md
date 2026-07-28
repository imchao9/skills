---
name: install-codex-auth-sync
description: Install, register, verify, and activate the Codex Auth Sync headless Agent on a remote macOS machine using a one-time enrollment code. Use when configuring CLIProxyAPI authentication sync on either Intel x86_64 or Apple Silicon arm64 Macs, diagnosing stale installer downloads, checking device registration, or completing the first sync after administrator approval.
x-provenance: local
x-owner: cm
x-source-note: created from the codex-auth-sync deployment workflow
---

# Install Codex Auth Sync

Install the headless CLIProxyAPI sync Agent from the production HTTPS service. Do not use the GUI `install.sh`; this workflow uses the architecture-aware `install-agent-v2.sh`.

## Boundaries

- Support macOS `arm64` and `x86_64`; stop on other systems.
- Manage CLIProxyAPI authentication only. Do not modify `~/.codex/config.toml`.
- Never place the enrollment code in Skill files, logs, reports, or persistent notes.
- Treat enrollment codes as one-time secrets. Prefer interactive input, `--code-stdin`, or a `0600` file.
- Never run a forced sync without explicit user confirmation. Forced sync backs up and replaces an existing local authentication file.

## Install

Resolve this Skill directory, then run its deterministic installer:

```bash
cd /absolute/path/to/install-codex-auth-sync
bash scripts/install.sh
```

For a non-interactive remote session, prefer stdin:

```bash
printf '%s\n' "$ENROLLMENT_CODE" | bash scripts/install.sh --code-stdin
```

If the code is already stored in a private file:

```bash
bash scripts/install.sh --code-file /absolute/path/to/enrollment-code.txt
```

The code file must be a regular file readable only by its owner. Do not accept a code from a command-line argument.

Expected evidence:

- Installer prints `Codex Auth Sync Agent Installer v2`.
- Detected architecture is `arm64` or `amd64`.
- `device.json` exists under `~/Library/Application Support/Codex Auth Sync/` with mode `0600`.
- Status output reports `registered: true` and a non-empty device ID.

Report only the architecture, registration state, user ID, device ID, and next action. Never output device tokens or authentication file contents.

## Administrator approval

After registration, tell the administrator to refresh the web console and approve the matching device. A pending device cannot download the shared authentication file.

After approval, run a safe first sync:

```bash
bash scripts/activate.sh
```

If it reports that the local authentication file changed, stop and ask whether the server account should replace it. Only after explicit confirmation run:

```bash
bash scripts/activate.sh --force --yes
```

## Inspect status

Use the status helper at any time:

```bash
bash scripts/status.sh
```

If output still contains the legacy message “仅支持 Apple 芯片 Mac”, the remote executor did not fetch `install-agent-v2.sh`. Run `scripts/install.sh` again; it adds a cache-busting query and validates the downloaded script before execution.
