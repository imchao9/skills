# Presentation Scorecard

Use this scorecard after renderer QA. A deck can pass screenshots and still fail this review.

Score each dimension from 1-5.

## Dimensions

1. Meeting goal / conversion goal
   - 1: unclear purpose.
   - 3: purpose is stated but not carried through.
   - 5: every section helps one decision or conversion.

2. Audience fit
   - 1: generic.
   - 3: roughly relevant.
   - 5: addresses the real concerns of each key audience.

3. Narrative closure
   - 1: collection of pages.
   - 3: logical sequence.
   - 5: problem, principles, option, tradeoff, risk, acceptance, next step are closed.

4. Source grounding
   - 1: plausible but untraceable.
   - 3: major claims traceable.
   - 5: decisive claims have source or explicit assumptions.

5. Technical correctness
   - 1: diagrams or claims are misleading.
   - 3: mostly credible but missing failure modes.
   - 5: boundaries, flows, data, security, observability, rollout and fallback are credible.

6. Diagram semantics
   - 1: decorative or unreadable.
   - 3: readable but underspecified.
   - 5: read order, node boundaries, edge semantics, legends and invariants are clear.

7. Visual readability
   - 1: cluttered or weak contrast.
   - 3: acceptable screenshots.
   - 5: readable at presentation distance, with controlled density and hierarchy.

8. Speaker usability
   - 1: presenter must improvise everything.
   - 3: notes exist but may read like docs.
   - 5: notes are natural, concise, and lead reviewers toward decisions.

9. Artifact completeness
   - 1: only final deck.
   - 3: deck plus screenshots.
   - 5: plan, claim ledger, diagram spec, style brief, deck, screenshots, QA, commands.

10. Failure interception
   - 1: no critical review.
   - 3: basic QA.
   - 5: catches pretty-but-empty, correct-but-unreadable, and plausible-but-unsourced outputs.

## Thresholds

- 45-50: strong candidate, ready for real use.
- 38-44: usable, but polish or evidence improvements needed.
- 30-37: draft only; do not treat as style exemplar.
- below 30: regenerate structure, not just CSS.

## Required Reviewer Notes

For any score below 4, record:

- what failed.
- why it matters.
- concrete fix.
- whether the fix belongs to structure, diagram, visual design, copy, or source evidence.
