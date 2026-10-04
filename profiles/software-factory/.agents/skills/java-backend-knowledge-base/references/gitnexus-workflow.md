# GitNexus Workflow

Use GitNexus for code facts: symbols, definitions, context, dependencies, clusters, and candidate processes.

## Index A Project

From target project root:

```bash
npx -y gitnexus@latest analyze . --skip-agents-md --skip-git --name <project-name>
npx -y gitnexus@latest list
```

Use `--skip-git` for local experiments when git history is not needed. Re-run after large code changes.

## Query Patterns

### Entrypoint Discovery

```bash
npx -y gitnexus@latest query "/orders/admin OrderController placeOrder" -r <project-name>
npx -y gitnexus@latest query "issueAfterSale reviewAfterSale state machine" -r <project-name>
```

Use results to find Controller/Client/Facade/Service entrypoints. Confirm in source files.

### Class Context

```bash
npx -y gitnexus@latest context OrderFacadeImpl -r <project-name>
npx -y gitnexus@latest context AfterSaleFacadeImpl -r <project-name>
```

Useful fields:

- `symbol`: class/method location.
- `outgoing.has_method`: methods on a class.
- `outgoing.has_property`: injected dependencies and important collaborators.
- `outgoing.implements`: interface contracts.
- `incoming`: callers/importers when available.

### State Machine Discovery

Search code first:

```bash
rg -n "StateFactory|StateContext|StateAdapter|enum class .*State|class .*State" .
```

Then query/context:

```bash
npx -y gitnexus@latest query "OrderSystemReviewApprovedState OrderSystemReviewRejectedState execute state machine" -r <project-name>
npx -y gitnexus@latest context OrderSystemReviewApprovedState -r <project-name>
```

### MQ And Job Discovery

Search code:

```bash
rg -n "RocketMQ|Kafka|Listener|Consumer|Producer|Topic|Tag|XxlJob|Scheduled" .
```

Then query:

```bash
npx -y gitnexus@latest query "RefundedMessageHandlingStrategy refund state machine message" -r <project-name>
```

## How To Use Results

GitNexus output is evidence, not final documentation.

Use it to create:

- `flow-map.md`: business stages plus Controller -> Facade -> Service -> State -> Message path.
- `business-rules.md`: validation rules, formulas, edge cases, and source evidence.
- `state-machine.md`: state enum, state class, `execute` action, next state.
- `impact-map.md`: DB writes, MQ producer/consumer, external clients, async jobs, idempotency, failure consequences, and regression checks.

Avoid shallow `code-map.md` output. Put semantic routing in `README.md`, `flow-map.md`, or `agent-guide/task-routing.md`.

Avoid writing raw JSON into the knowledge base. Summarize into stable names and file paths.

## Minimum Usage For P0/P1 Flow Documentation

For each P0/P1 flow:

1. Run a `query` combining the business verb and likely code names, e.g. `placeOrder OrderFacadeImpl OrderServiceImpl payment`.
2. Run `context` on at least the main class or factory when it resolves, e.g. `OrderFacadeImpl`, `OrderServiceImpl`, `AfterSaleStateFactory`.
3. If exact method context fails, use `query` to locate the method symbol and then read the source file directly.
4. Convert candidates into a source-confirmed chain: endpoint/client -> controller -> aspect/validator -> facade -> service -> strategy/state/factory -> mapper/table -> MQ/job/external client.
5. Put that chain into `flow-map.md` and a module-local Mermaid code-flow diagram.
6. Mention in the final summary which GitNexus queries were used or why GitNexus was unavailable.

Do not stop at a GitNexus process summary. Process summaries can be noisy; source-confirm the final business claims.

## Known Limitations

- Natural-language `query` can return noisy `processes`; treat them as candidates.
- `context` is usually more reliable for class-level maps.
- It cannot decide business importance by itself.
- It cannot explain hidden product/operations rules that are not in code.
- It should be paired with human confirmation for P0/P1 business semantics.
