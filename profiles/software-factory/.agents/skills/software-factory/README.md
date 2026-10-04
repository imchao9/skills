# Codex software-factory adapter

This is a reviewable prototype of the Codex adaptation discussed in the workflow audit. It is deliberately small:

- `SKILL.md` is the one default router.
- `references/codex-adapter.md` maps pstack's Cursor concepts to Codex artifacts and threads.
- `scripts/factory.py` creates a durable work directory and emits worker briefs; it never launches a cloud task or merges code by itself.

Try it in a scratch repository:

```bash
python3 software-factory/scripts/factory.py init checkout-search-001 \
  --goal 'Add server-side filtering to checkout search'
python3 software-factory/scripts/factory.py unit checkout-search-001 unit-01 \
  --scope 'src/search/**; tests/search/**' \
  --acceptance 'Existing queries remain compatible; filtered results are deterministic' \
  --verify 'npm test -- search && npm run typecheck'
python3 software-factory/scripts/factory.py brief checkout-search-001 unit-01 \
  --goal 'Implement the filter' \
  --scope 'src/search/**; tests/search/**' \
  --acceptance 'Existing queries remain compatible; filtered results are deterministic' \
  --verify 'npm test -- search && npm run typecheck'
python3 software-factory/scripts/factory.py status checkout-search-001

# Activate only the implementation stage in a project
python3 software-factory/scripts/factory.py activate \
  --skills-repo /Users/cm/Documents/Me/Skills \
  --target /path/to/project \
  --stage execute \
  --pack frontend
```

The resulting brief is the input to a Codex local or cloud worker. The main agent still owns gates and external actions.
