# Execution backends

## Decision table

| Backend | Separate model configuration | Keeps AI Test assets and reports | Intended use |
|---|---:|---:|---|
| `framework-only` | No | Yes, for non-visual assets | Planning, TypeScript case generation, knowledge recall, deterministic audits, report parsing |
| `midscene` | Yes | Yes | Maintained UI execution, visual localization, semantic assertions, design walkthroughs, browser/desktop/mobile runners |
| `codex-native-spike` | No separate Midscene key | No | Short-lived browser, Chrome, or desktop exploration inside the current Codex task |

## Why Midscene still needs a model endpoint

The framework validates `MIDSCENE_MODEL_BASE_URL`,
`MIDSCENE_MODEL_API_KEY`, `MIDSCENE_MODEL_NAME`, and
`MIDSCENE_MODEL_FAMILY` before execution. Its Web, computer, Android, and iOS
runners instantiate Midscene agents, and design review calls an
OpenAI-compatible `/chat/completions` endpoint with a bearer key.

The model running the current Codex task is not a credential or endpoint that a
local Node.js child process can inherit. A skill can tell Codex which command
to run, but it does not turn Codex's session model into
`MIDSCENE_MODEL_API_KEY`.

Planning and insight model variables are optional in this repository and fall
back to the primary Midscene model. The primary four variables are required by
the current configuration schema.

## Codex-native spike boundary

Codex may use its available Browser, Chrome, or Computer Use tools to perform
an interactive exploratory check without Midscene model variables. This is a
different backend:

- it does not execute the repository's Midscene agents;
- it does not produce the canonical Midscene cache or HTML evidence contract;
- it does not provide Android/iOS/Harmony runner parity;
- it must not be promoted to a maintained pass/fail result without a separate
  agreed evidence contract.

Use this backend to learn the page, reproduce a simple issue, or draft a future
case. Use Midscene when the requested outcome is a maintained, repeatable AI
Test run.
