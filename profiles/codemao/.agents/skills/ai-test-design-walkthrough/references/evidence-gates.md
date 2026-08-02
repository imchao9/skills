# Design Walkthrough Evidence Gates

Use three separate outcomes:

1. **Execution** — Did the maintained case run successfully?
2. **Reachability** — Does `design-walkthrough.json` prove the intended target state was reached?
3. **Design review** — What does the visual evidence say?

The design verdicts mean:

- `DESIGN_REVIEW_PASSED`: evidence supports design compliance.
- `DESIGN_REVIEW_ADJUST`: evidence shows actionable visual/interaction differences.
- `DESIGN_REVIEW_NEEDS_REVIEW`: evidence localizes differences but product/design intent needs confirmation.
- `DESIGN_REVIEW_UNKNOWN`: evidence cannot support a design judgment.

Never use source code similarity as design proof. Inspect the Figma baseline and matching actual screenshot for each important checkpoint. A checkpoint missing its matching actual state stays unknown; do not substitute another screenshot.

The wrapper's acceptance event checks artifact existence and top-level target/verdict fields. The agent still owns visual inspection and issue wording.
