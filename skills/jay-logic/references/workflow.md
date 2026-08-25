# Jay Logic Workflow

Use Jay Logic as an audit navigation layer.

## Recommended Reading Order

1. `functions.md`: identify high-value functions and their state/external dependencies.
2. `entry-flows.md`: follow callable functions to state writes and external calls.
3. `line-links.tsv`: answer line-specific relation questions.
4. Mermaid files: quickly inspect graph shape.
5. `jay-logic.json`: use for custom scripts or downstream skill consumption.

## Interpretation

- `calls` means a function-like expression was found and resolved to an in-repo function when possible.
- `external_call` means the call could not be resolved to an in-repo function or uses dotted/module syntax.
- `reads` and `writes` are static lexical relations. Confirm complex aliasing manually before relying on them.
- `guards` points from a function to a guard node such as `require`, `assert`, or `if ... revert`.
- `precondition_written_by` links a writer function to a guarded function when one function writes state used by another function's guard.
- Runtime details are stored in node metadata. For Move, check entry/resource/capability fields. For Anchor, check context/account/PDA/signer/CPI fields.

## Audit Use

Good follow-up questions:

- Which functions write the state used by this guard?
- Which entry points can reach this external call?
- Which lines are related to this balance/accounting update?
- Which state variables are only written by admin or keeper functions?

Do not treat the graph as exploit proof. Use it to select paths, then validate reachability, permissions, values, and impact in the source and tests.
