# Frontend Review Checklist

Use this reference for a final self-review or a read-only review of frontend changes.
Apply only checks relevant to the change and report concrete findings rather than repeating the checklist.

## Behavior and state

- Confirm the implementation matches the requested user behavior.
- Check loading, empty, error, disabled, forbidden, success, and retry states where applicable.
- Check whether form input and useful context survive recoverable failures.
- Check duplicate clicks, request races, stale responses, cancellation, and optimistic rollback.
- Check route changes, refresh, back, and forward when state belongs in the URL.

## Data and API contract

- Compare runtime response fields with frontend types and mapping code.
- Check nullability, optional fields, unknown enums, dates, numeric precision, and response envelopes.
- Confirm errors transition to intentional UI state instead of being swallowed.
- Confirm pending state always settles on success, failure, cancellation, and unmount.
- Confirm mock fixtures include abnormal and boundary data, not only the happy path.

## Component design and impact

- Search all callers of changed shared components, hooks, utilities, and types.
- Check changed defaults, props, events, CSS selectors, and context values for backward compatibility.
- Confirm state has one authoritative owner and derived values are not mirrored unnecessarily.
- Check that component responsibilities and public contracts remain understandable.
- Reject speculative abstractions that are not required by current behavior.

## Type and runtime safety

- Flag broad assertions, unchecked casts, non-null assertions, and silent fallbacks that conceal invalid data.
- Check list keys, effect dependencies, stale closures, cleanup, memoization, and conditional hooks.
- Check error boundaries and suspense behavior when the repository uses them.
- Check unsafe HTML, URL construction, client-side permission assumptions, and sensitive data exposure.

## Visual and interaction quality

- Inspect real rendering at target desktop and mobile viewports.
- Check overflow, overlap, clipping, wrapping, alignment, density, and persistent action visibility.
- Check hover, active, focus, disabled, loading, empty, and error visuals.
- Check keyboard reachability, focus order, focus restoration, labels, semantics, contrast, and reduced motion.
- Confirm that visual changes reuse repository tokens and components.

## Performance

- Look for avoidable render loops, unstable props, expensive work during render, oversized bundles, and unbounded lists.
- Require measurement before claiming a performance regression or improvement.
- Prefer pagination, virtualization, deferred work, or memoization only when the observed workload justifies it.

## Verification evidence

- Run the relevant lint, typecheck, tests, and production build.
- Exercise the real browser path for user-visible changes.
- Confirm console and network behavior.
- State which viewports and states were observed.
- Separate passed checks, failed checks, skipped checks, and residual risks.

## Finding format

For each actionable issue, report:

1. Severity based on user or regression impact.
2. File and tight location.
3. The observable failure scenario.
4. Evidence from code or runtime behavior.
5. The smallest safe correction.

Do not report general preferences as defects without an observable consequence or repository rule.
