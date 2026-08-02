# Verdict Model

Judge these axes independently:

| Axis | Values | Meaning |
| --- | --- | --- |
| `executionStatus` | `passed`, `failed`, `error`, `skipped`, `not-run` | What the runner recorded |
| `evidenceStatus` | `complete`, `partial`, `unusable` | Whether required evidence exists and can be inspected |
| `targetStatus` | `reached`, `not-reached`, `unknown` | Whether the intended page/state was visibly reached |
| `businessStatus` | `verified-pass`, `verified-fail`, `unverified` | What the evidence proves about the expected behavior |

Map the axes to one overall verdict:

- `VERIFIED_PASS`: runner passed, evidence is complete, target was reached, and expected business behavior is visibly proven.
- `VERIFIED_FAIL`: target was reached and usable evidence proves the business behavior is wrong.
- `INVALID_RUN`: the intended target was not reached, execution was skipped/not run, or environment/test-data/case failure made the run invalid as a product judgment.
- `INCONCLUSIVE`: evidence is missing, partial, conflicting, or insufficient to distinguish a product failure from another cause.

`VERIFIED_FAIL` is stronger than “test failed.” Use it only when the evidence shows the product behavior at the intended target.
