#!/usr/bin/env python3
"""Print a credential-routing plan without accepting or printing secrets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PRESETS = {
    "M26A": {"profile": "macos26-arm64", "architecture": "arm64"},
    "M15A": {"profile": "macos15-arm64", "architecture": "arm64"},
    "M15I": {"profile": "macos15-x64", "architecture": "x86_64"},
    "M14I": {"profile": "macos14-x64", "architecture": "x86_64"},
}

SCOPES = {
    "LITE": {"base": True, "openclaw": True, "codex_cli": True, "validate": True},
    "CORE": {
        "base": True,
        "openclaw": True,
        "codex_cli": True,
        "secrets": True,
        "validate": True,
    },
    "FULL": {
        "base": True,
        "openclaw": True,
        "codex_cli": True,
        "secrets": True,
        "extras": True,
        "office_skills": True,
        "validate": True,
    },
}


def present(value: str) -> bool:
    return value == "present"


def load_spec(path: str | None) -> dict:
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read install spec: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("Install spec must be a JSON object.")
    forbidden = {"key", "token", "secret", "password", "code"}
    for name in data.get("credentials", {}):
        if any(word in name.lower() for word in forbidden) and name not in {
            "auth_sync_code_present"
        }:
            raise SystemExit("Install spec may contain credential presence only, never values.")
    return data


def active_components(components: dict) -> list[str]:
    return [name for name, enabled in components.items() if enabled]


def parse_preset(value: str | None) -> dict:
    if not value:
        return {}
    target, network, auth, scope = value.upper().split("-", 3)
    if target not in PRESETS:
        raise SystemExit(f"Unknown target code: {target}")
    if network not in {"VPN", "DIRECT"}:
        raise SystemExit(f"Unknown network code: {network}")
    if auth not in {"MR", "SYNC"}:
        raise SystemExit(f"Unknown auth code: {auth}")
    if scope not in SCOPES:
        raise SystemExit(f"Unknown scope code: {scope}")
    components = dict(SCOPES[scope])
    components["clash_party"] = network == "VPN"
    components["auth_sync"] = auth == "SYNC"
    return {
        "preset": value.upper(),
        "target": PRESETS[target],
        "network": network.lower(),
        "route": "matrixrouter" if auth == "MR" else "auth-sync",
        "components": components,
    }


def main() -> None:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("--spec")
    bootstrap.add_argument("--preset")
    spec_args, _ = bootstrap.parse_known_args()
    if spec_args.spec and spec_args.preset:
        raise SystemExit("Use either --spec or --preset, not both.")
    spec = load_spec(spec_args.spec)
    preset = parse_preset(spec_args.preset)
    if preset:
        spec = preset
    credentials = spec.get("credentials", {})
    components = spec.get("components", {})

    parser = argparse.ArgumentParser()
    parser.add_argument("--spec")
    parser.add_argument("--preset")
    parser.add_argument("--mode", choices=("auto", "matrixrouter", "auth-sync"), default=spec.get("route", "auto"))
    parser.add_argument("--matrixrouter-openai", choices=("present", "absent"), default=credentials.get("matrixrouter_openai", "absent"))
    parser.add_argument("--matrixrouter-anthropic", choices=("present", "absent"), default=credentials.get("matrixrouter_anthropic", "absent"))
    parser.add_argument("--auth-sync-code", choices=("present", "absent"), default=credentials.get("auth_sync_code_present", "absent"))
    parser.add_argument("--auth-sync-approved", choices=("yes", "no"), default=credentials.get("auth_sync_approved", "no"))
    parser.add_argument("--need-openclaw", action="store_true", default=components.get("openclaw", False))
    args = parser.parse_args()

    matrixrouter_ready = present(args.matrixrouter_openai) and (
        not args.need_openclaw or present(args.matrixrouter_anthropic)
    )
    auth_sync_ready = present(args.auth_sync_code)
    route = args.mode
    blockers: list[str] = []

    if route == "auto":
        if matrixrouter_ready:
            route = "matrixrouter"
        elif auth_sync_ready:
            route = "auth-sync"
        else:
            route = "blocked"

    if route == "matrixrouter":
        if not present(args.matrixrouter_openai):
            blockers.append("MatrixRouter Codex route requires an OpenAI-compatible key.")
        if args.need_openclaw and not present(args.matrixrouter_anthropic):
            blockers.append("OpenClaw Claude route requires a MatrixRouter Anthropic key.")
    elif route == "auth-sync":
        if not auth_sync_ready:
            blockers.append("Auth Sync route requires a valid one-time enrollment code.")
        if args.need_openclaw and present(args.matrixrouter_anthropic):
            blockers.append(
                "OpenClaw Claude needs a split configuration; do not run a combined CLIProxy writer."
            )
    else:
        blockers.append("No usable credential route was supplied.")

    default_components = {
        "base": True,
        "openclaw": args.need_openclaw,
        "codex_cli": True,
        "secrets": False,
        "clash_party": False,
        "auth_sync": route == "auth-sync",
        "extras": False,
        "office_skills": False,
        "validate": True,
    }
    default_components.update(components)
    selected = active_components(default_components)
    waves = [
        {
            "name": "gate",
            "parallel": False,
            "tasks": ["preflight architecture/disk/route", "discover selected model IDs"],
        },
        {
            "name": "transfer",
            "parallel": True,
            "tasks": ["download package with resume", "prepare zstd bootstrap or explicit fallback"],
        },
        {
            "name": "core",
            "parallel": False,
            "tasks": ["verify and extract package", "install base apps and runtime", "install global npm CLIs"],
        },
        {
            "name": "configuration",
            "parallel": False,
            "tasks": ["restore selected secrets", "write selected route configuration", "restart gateway"],
        },
        {
            "name": "acceptance",
            "parallel": False,
            "tasks": ["Codex HELLO_OK", "OpenClaw HELLO_OK", "record versions and durations"],
        },
    ]
    deferred = [name for name in ("extras", "office_skills") if default_components.get(name)]
    if deferred:
        waves.append(
            {
                "name": "deferred_optional",
                "parallel": False,
                "tasks": [f"install {name} after acceptance" for name in deferred],
            }
        )

    plan = {
        "preset": spec.get("preset"),
        "target": spec.get("target"),
        "network": spec.get("network", "custom"),
        "route": route,
        "ready": not blockers,
        "blockers": blockers,
        "selected_components": selected,
        "models": spec.get("models", {}),
        "codex": (
            "MatrixRouter Responses; query /v1/models before selecting a model."
            if route == "matrixrouter"
            else "CLIProxy backed by Codex Auth Sync; register, approve, then safe-sync."
            if route == "auth-sync"
            else "No configuration change."
        ),
        "openclaw": (
            "MatrixRouter Anthropic Messages; query models and use the selected Claude ID."
            if route == "matrixrouter" and args.need_openclaw
            else "No OpenClaw Claude configuration requested."
        ),
        "auth_sync_admin_approval_needed": route == "auth-sync" and args.auth_sync_approved == "no",
        "zstd_preflight": "Run scripts/check_zstd.sh before downloading tar.zst archives.",
        "waves": waves,
        "layer_download_jobs": 1,
        "layer_download_note": "Keep one downloader by default; raise only after measuring bandwidth and disk contention.",
        "secrets_accepted": False,
    }
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
