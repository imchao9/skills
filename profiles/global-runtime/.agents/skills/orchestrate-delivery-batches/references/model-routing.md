# Model routing

Route by uncertainty and blast radius, then by latency and cost. Always inspect the runtime's current model/role list before assigning names.

| Work shape | Preferred tier | Typical reasoning | Independent role |
|---|---|---|---|
| External contract, protocol inference, data migration, concurrency, auth, cross-cutting state machine | strongest frontier | high to maximum | reviewer and verifier when available |
| Clear vertical product slice with bounded API/UI/store work | balanced agentic | medium to high | verifier for user-visible or data-sensitive work |
| Read-only exploration, file inventory, mechanical rewrite, focused test execution, docs | fast or cost-efficient | low to medium | optional |
| Final integration across several agents | strongest frontier | high | verifier distinct from implementers |

When the runtime exposes a family such as `sol`, `terra`, and `luna`:

- use `sol`-class capability for the strongest-frontier rows;
- use `terra`-class capability for bounded implementation;
- use `luna`-class capability for fast exploration and mechanical work;
- prefer a dedicated `reviewer` or `verifier` role over choosing a model name manually when that role already fixes an appropriate model and reasoning level.

These names are examples, not a permanent allowlist. If availability or supported reasoning changes, preserve the tier decision and select the current equivalent.

## Routing checks

Before dispatch, answer:

1. What uncertainty makes this ticket difficult?
2. What is the blast radius if it is wrong?
3. Is the work generative, mechanical, or independent acceptance?
4. Does the model need inherited context, or is a fresh brief safer?
5. Is an override worth its latency/cost relative to inheriting the parent?

If no answer justifies an override, inherit the parent model.
