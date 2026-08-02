# Failure Taxonomy

Classify the dominant cause only after evidence review and include confidence (`high`, `medium`, or `low`).

| Category | Use when evidence shows |
| --- | --- |
| `environment` | app/device/browser/model service/network/configuration could not provide the required runtime |
| `test-data` | account, fixture, package, course, permissions, or prepared state is missing or wrong |
| `case` | maintained steps, selector/prompt, wait, assertion, or setup does not represent the intended behavior |
| `model` | model call or interpretation failed independently of visible product behavior |
| `framework` | loader, orchestrator, evidence collection, report generation, or platform adapter malfunctioned |
| `product` | the intended state was reached and evidence shows actual product behavior violates the expectation |
| `requirement` | source expectation is contradictory, incomplete, or not decidable |
| `unknown` | evidence cannot distinguish the cause |

Guardrails:

- `ai_assert_failed` identifies the runner symptom, not a product root cause.
- `runtime_error` identifies an exception path, not necessarily a framework defect.
- Login failure is usually `environment`, `test-data`, or `case` until product evidence proves otherwise.
- Use `unknown` instead of guessing.
