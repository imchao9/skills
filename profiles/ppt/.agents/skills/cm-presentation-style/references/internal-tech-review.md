# Internal Technical Review Deck

Use this mode for architecture review, technical方案评审, implementation strategy, migration plans, incident reviews, and engineering decision meetings.

## Goal

Make a technical decision easier to approve, reject, or reshape.

The deck should answer:

- What is the decision?
- Why now?
- What is the current failure mode?
- What are the design principles?
- What is the proposed architecture?
- What are the tradeoffs and non-goals?
- How will this be delivered and verified?
- What exactly should reviewers approve?

## Narrative Shape

Recommended 8-12 slide arc:

1. Decision title: literal topic, not slogan.
2. Current problem: one real pain, not a generic background page.
3. Evaluation principles: 3-5 constraints that drive later choices.
4. Target architecture: boundaries, ownership, sync/async paths.
5. Core flow: online request path or user journey.
6. State/data/event path: persistence, counters, audit, observability.
7. MVP scope: in / out, phased rollout.
8. Risks and mitigations: failure modes, fallback, security, operations.
9. Acceptance gates: functional, stability, observability, rollout.
10. Decision asks: the concrete approvals needed.

## CM Style Rules

- Use a light technical canvas with restrained grid, high-contrast text, and one narrow vertical accent.
- Keep one primary idea per slide.
- Put dense reasoning in speaker notes, not visible text.
- Prefer tables and diagrams over prose when comparing options, gates, or ownership.
- Use diagrams only when they clarify boundaries or flow. A diagram without a read order fails.
- Avoid hero marketing composition, oversized decorative imagery, and slogan-only slides.

## Required Evidence Files

- `claim_ledger.md`: every decisive claim must be traceable to source, code, logs, screenshots, or an explicit assumption.
- `diagram_spec.md`: every technical diagram must define nodes, edges, flow types, read order, and invariants.
- `qa_report.md`: must include review scorecard, not only screenshot checks.

## Passing Bar

The reviewer should be able to say:

- I know what decision is requested.
- I can explain the architecture from the diagrams.
- I can see what is excluded from MVP.
- I know how this will be tested, rolled out, observed, and rolled back.
- I can challenge any major claim because its source or assumption is visible.
