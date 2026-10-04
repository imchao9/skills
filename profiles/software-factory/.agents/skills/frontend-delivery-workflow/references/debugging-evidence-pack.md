# Frontend Debugging Evidence Pack

Use this reference when the symptom exists only in the browser or depends on interaction, layout, runtime state, or a backend response.

## Capture the symptom

Record:

- Exact reproduction steps from a stable starting state.
- Expected result and actual result.
- Route, account or permission role, browser, and viewport.
- Frequency and whether reload, navigation, or timing changes it.
- The smallest recent diff or dependency change that may be related.

Preserve screenshots, traces, or logs as local evidence when useful.
Do not expose cookies, tokens, authorization headers, personal data, or signed URLs.

## Capture console evidence

Collect the complete actionable error, component stack, rejected promise, and relevant warning.
Distinguish the first causal error from follow-on render failures.
Check whether error handling logs a failure but returns undefined or leaves pending state active.

## Capture network evidence

Record the request method, URL path, status, sanitized payload, sanitized response shape, timing, and initiator.
Compare the runtime response with frontend types and mapping code.
Check:

- Renamed or missing fields.
- Nullable fields treated as required.
- String, number, boolean, or date mismatches.
- Unknown enum values.
- HTTP success carrying a business error.
- Response envelopes that differ between environments.
- Retry, cancellation, cache, and duplicate-request behavior.

Never infer a correct integration from status 200 alone.

## Capture layout evidence

For CSS or responsive defects, record:

- Screenshot at the failing viewport.
- Target element or component.
- Expected and actual geometry.
- Computed display, position, width, height, overflow, z-index, flex, and grid values as relevant.
- Parent layout constraints and the active media query.
- The style rule that wins in the browser.

Use browser-computed facts to distinguish a wrong rule, overridden rule, containing-block issue, intrinsic-size issue, stacking context, or breakpoint problem.

## Diagnose

Build three to five ranked, falsifiable hypotheses.
For each hypothesis, state the evidence that would confirm or refute it.
Test the cheapest discriminating observation first.
Change one variable at a time and preserve the reproduction loop.

Prefer this result format:

| Rank | Hypothesis | Supporting evidence | Disconfirming test | Result |
| --- | --- | --- | --- | --- |

Do not patch multiple speculative causes at once.
Do not rewrite the page to hide a local defect.

## Close the loop

After fixing:

1. Re-run the original reproduction steps.
2. Exercise the nearest adjacent states.
3. Confirm console and network behavior.
4. Check the failing and neighboring viewports.
5. Add a stable regression check when the public seam supports one.
6. Remove temporary instrumentation.
