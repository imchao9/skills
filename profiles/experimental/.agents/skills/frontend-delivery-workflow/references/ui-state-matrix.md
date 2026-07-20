# UI State Matrix

Use this reference before implementing stateful pages, forms, tables, dialogs, mutations, or coordinated components.

## Build the matrix

List only states that can produce a distinct user-visible result or interaction rule.
Use this shape:

| State | Trigger | Visible result | Enabled actions | Exit or recovery | Verification |
| --- | --- | --- | --- | --- | --- |
| Initial | Route opens | Stable shell or intentional placeholder | Context dependent | Start request or accept input | First render has no stale content |
| Loading | Request begins | Progress feedback without layout collapse | Cancel if supported | Resolve or fail | Slow request remains understandable |
| Success | Valid data arrives | Complete content | Primary actions enabled | Navigate or mutate | Representative data renders |
| Empty | Valid empty result | Empty explanation and useful next action | Create, clear filter, or retry | User action | Empty is distinct from loading |
| Error | Request fails | Actionable error message | Retry or safe navigation | Successful retry | Failure does not become a blank page |
| Forbidden | Permission blocks access | Permission-specific state | Safe navigation | Permission changes or leave | Protected action is unavailable |
| Pending mutation | User submits | Progress and duplicate-submit protection | Cancel if safe | Success or failure | Repeated clicks do not duplicate work |
| Mutation failure | Mutation rejects | Input preserved and error explained | Retry or edit | Successful retry | Optimistic state rolls back when required |

Add domain-specific states such as partial data, stale data, offline, rate limited, expired session, or destructive confirmation only when relevant.

## Assign state ownership

Use this decision order:

1. Keep state inside one component when no sibling or external consumer needs it.
2. Lift state to the nearest common owner when multiple children coordinate through it.
3. Put shareable navigation state in the URL when reload, back, forward, or sharing should preserve it.
4. Keep remote data in the repository's server-cache layer when one exists.
5. Use global state only for cross-route or application-wide behavior that cannot remain local.

Record complex ownership explicitly:

| State | Owner | Consumers | Write events | Persistence | Reason |
| --- | --- | --- | --- | --- | --- |

Avoid mirrored state when a value can be derived from one authoritative source.
Avoid allowing children to mutate parent-owned state through hidden shared objects.

## Define component contracts

For each non-trivial component, record:

- Responsibility and non-responsibilities.
- Required and optional inputs.
- Emitted events and payload shape.
- Controlled versus uncontrolled behavior.
- Loading, empty, error, disabled, and read-only behavior.
- Accessibility semantics and focus behavior.

## Check async transitions

Walk through the event sequence for search, pagination, filters, selection, editing, submission, cancellation, and undo.
Check:

- Old requests resolving after new requests.
- Duplicate submission or rapid repeated actions.
- State updates after unmount.
- Optimistic updates that need rollback.
- Cached data becoming stale after mutation.
- A rejected promise being logged but not represented in UI state.

Turn the final matrix into implementation and test checkpoints.
