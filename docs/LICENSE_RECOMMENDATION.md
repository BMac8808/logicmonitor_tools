# License Recommendation (pending owner decision)

No `LICENSE` file has been added. The repository owner must choose one. Until then,
default copyright applies and others cannot legally reuse or redistribute the code.

## Recommendation: Apache License 2.0

| Consideration | Apache-2.0 | MIT |
|---------------|------------|-----|
| Permissive (commercial use, modification) | Yes | Yes |
| Explicit patent grant from contributors | **Yes** | No |
| Explicit trademark clause (no right to use names/marks) | **Yes** (§6) | No |
| Requires stating significant changes | Yes | No |
| Simplicity | Longer text | Very short |

Apache-2.0 is the better fit because:

1. The repository sits next to a commercial product's ecosystem. The trademark clause
   states clearly that the license grants no right to use LogicMonitor or contributor
   names and marks.
2. Contributors may work for vendors, partners or customers; the patent grant protects
   downstream users.
3. Many enterprises already approve it for internal tooling.

MIT is a reasonable alternative if the owner prefers the shortest possible license.

## To adopt

1. Add the unmodified license text as `LICENSE` at the repository root.
2. Replace the "License" section in `README.md`.
3. Optionally add `license = "Apache-2.0"` to tool manifests (`pyproject.toml`,
   `package.json`).
