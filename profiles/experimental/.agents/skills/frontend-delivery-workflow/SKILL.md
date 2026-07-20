---
name: frontend-delivery-workflow
description: Plan, implement, debug, review, and visually verify production frontend changes in an existing web codebase. Use for React, Vue, Next.js, Vite, or similar frontend feature work involving page or component implementation, UI state design, API integration, responsive behavior, design-to-code, browser-side debugging, shared-component changes, or frontend regression review.
x-provenance: local-candidate
x-owner: cm
x-source-note: distilled from a local AI frontend development and debugging demo; original source ownership not fully confirmed
---

# Frontend Delivery Workflow

Deliver frontend changes through observable user states and real browser evidence.
Adapt to the repository's framework, conventions, component library, and validation commands instead of imposing a new stack.

## Establish the delivery contract

Read repository guidance, package scripts, relevant components, routes, API clients, types, tests, and design tokens before proposing code.
Define:

- Scope and explicit non-goals.
- The user-visible behavior and public seam.
- Required UI states and transitions.
- Existing components, hooks, utilities, and tokens to reuse.
- Verification commands and browser scenarios.
- Important responsive, accessibility, permission, and API edge cases.

Do not start with code when component boundaries, state ownership, API shape, or acceptance behavior are still ambiguous.
Record narrow assumptions when they are reversible.
Ask only when an unresolved choice materially changes behavior or architecture.

## Choose the path

- For a new page or feature, follow all phases.
- For a component change, start with caller and impact analysis, then follow the relevant phases.
- For an API integration, emphasize response-to-UI mapping and abnormal fixtures.
- For a UI or CSS bug, use the debugging evidence pack and reproduce before editing.
- For design-to-code, build a design-to-component map before generating markup or styles.
- For a review-only request, do not edit; use the review checklist against the supplied diff or fixed point.

## Phase 1: Model the interface

Sketch the component tree and assign one clear responsibility to each component.
Place state with the narrowest owner that serves every consumer.
Distinguish local UI state, URL state, form state, server cache, and genuinely global state.
Define props inputs, events outputs, async transitions, and cancellation or stale-response behavior.

Read [ui-state-matrix.md](references/ui-state-matrix.md) for pages, forms, tables, dialogs, mutations, or multi-component interactions.
Produce the state matrix before implementation when three or more meaningful states exist.

## Phase 2: Implement a vertical slice

Implement the smallest user-complete path through the existing public seam.
Prefer repository components and tokens over new abstractions.
Keep data acquisition, state transitions, and presentation boundaries visible.

Cover relevant states as part of the slice:

- Initial and loading.
- Success with representative data.
- Empty or absent optional data.
- Error with recovery or retry.
- Disabled, forbidden, or read-only.
- Mutation pending, success, and failure.

Create fixtures that include long text, missing optional fields, unknown enum values, empty collections, malformed responses, and permission failures when applicable.
Do not let a caught error silently return undefined to rendering code.
Either propagate the error, return an intentional fallback, or transition into an explicit error state.

For async interactions, consider duplicate submission, request ordering, unmounting, cancellation, optimistic rollback, and stale cache updates.
Preserve keyboard behavior, focus order, labels, semantics, and existing accessibility conventions.

## Phase 3: Debug from evidence

Reproduce the exact symptom through the closest user-facing path.
Collect browser facts before forming a final diagnosis.
Read [debugging-evidence-pack.md](references/debugging-evidence-pack.md) for blank pages, ineffective actions, CSS failures, stale state, API mismatches, or intermittent UI behavior.

Rank falsifiable causes and test them in order.
Change one variable at a time.
Prefer the smallest fix that addresses the verified cause and preserves surrounding behavior.
Add a regression test at a stable public seam when one exists.

## Phase 4: Verify in layers

Run the repository's relevant formatter or lint, typecheck, tests, and production build.
For user-visible changes, also run the application and inspect the real interface.

Verify at minimum:

- The primary user path completes.
- Loading, empty, error, disabled, and mutation states behave as required.
- Console has no new actionable errors or warnings.
- Network method, URL, payload, status, response shape, and retry behavior match the contract.
- Target viewport sizes do not overflow, overlap, clip, or hide actions.
- Keyboard and focus behavior remain usable.

Do not claim visual verification without observing the rendered interface or screenshots.
Do not claim backend integration from mocked data alone.

For Figma, screenshots, or other design sources, read [design-to-code-checklist.md](references/design-to-code-checklist.md).

## Phase 5: Review the delivered change

Search every caller before changing shared component props, defaults, events, or styling behavior.
Review the final diff against the delivery contract and repository standards.
Read [frontend-review-checklist.md](references/frontend-review-checklist.md) before handoff.

Prioritize correctness and regression risks over stylistic preferences.
Report findings with file and location, observable impact, evidence, and a concrete fix.
Separate verified results from unverified risks.

## Handoff

Lead with the delivered behavior.
Report:

1. Changed files and the user-visible result.
2. Verification commands and their actual outcomes.
3. Browser scenarios and viewport states inspected.
4. API or mock evidence used.
5. Remaining risks, skipped checks, or assumptions.

Never describe a failed build, missing browser check, or mocked integration as complete.
