#!/usr/bin/env python3
"""Collect a no-secret install brief and print an install card plus JSON spec."""

from __future__ import annotations

import json


def choose(label: str, values: tuple[str, ...]) -> str:
    prompt = f"{label} ({'/'.join(values)}): "
    while True:
        value = input(prompt).strip().upper()
        if value in values:
            return value
        print(f"Please choose one of: {', '.join(values)}")


def yes_no(label: str) -> str:
    return "present" if choose(label, ("YES", "NO")) == "YES" else "absent"


def main() -> None:
    print("OpenClaw install intake. Do not enter keys, tokens, or enrollment codes here.")
    target = choose("Target", ("M26A", "M15A", "M15I", "M14I"))
    network = choose("Network", ("VPN", "DIRECT"))
    auth = choose("Authentication", ("MR", "SYNC"))
    scope = choose("Scope", ("LITE", "CORE", "FULL"))
    credentials: dict[str, str]
    if auth == "MR":
        credentials = {
            "matrixrouter_openai": yes_no("MatrixRouter OpenAI-compatible key available"),
            "matrixrouter_anthropic": yes_no(
                "MatrixRouter Anthropic key available for OpenClaw"
            ),
            "auth_sync_code_present": "absent",
            "auth_sync_approved": "no",
        }
    else:
        credentials = {
            "matrixrouter_openai": "absent",
            "matrixrouter_anthropic": "absent",
            "auth_sync_code_present": yes_no("Valid Auth Sync enrollment code available"),
            "auth_sync_approved": "yes"
            if choose("Administrator has approved this device", ("YES", "NO")) == "YES"
            else "no",
        }

    card = f"{target}-{network}-{auth}-{scope}"
    spec = {
        "preset": card,
        "credentials": credentials,
        "note": "Credential presence only; enter secret values only during protected execution.",
    }
    print(f"\nINSTALL_CARD={card}")
    print(json.dumps(spec, indent=2))
    print(
        "\nNext: python3 scripts/plan_route.py "
        f"--preset {card} "
        f"--matrixrouter-openai {credentials['matrixrouter_openai']} "
        f"--matrixrouter-anthropic {credentials['matrixrouter_anthropic']} "
        f"--auth-sync-code {credentials['auth_sync_code_present']} "
        f"--auth-sync-approved {credentials['auth_sync_approved']}"
    )


if __name__ == "__main__":
    main()
