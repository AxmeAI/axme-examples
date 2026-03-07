# Example Matrix

This repository contains two example families:

- **Cloud examples**: runnable orchestration scenarios (require AXME Cloud)
- **Protocol examples**: AXP-only compatibility scenarios (no AXME Cloud runtime required)

## Cloud matrix

All cloud scenarios require API key from the landing page.
`AXME_BASE_URL` can be used as an optional override for staging/dev.

| Scenario | Python | TypeScript | Go | Java | .NET |
|---|---|---|---|---|---|
| approval-workflow | full | full | snippet | snippet | snippet |
| external-callback | full | full | snippet | snippet | snippet |
| retry-workflow | full | full | snippet | snippet | snippet |
| multi-service-coordination | full | full | snippet | snippet | snippet |

Legend:

- `full`: runnable project in `examples/<scenario>/<language>`
- `snippet`: short usage sample in `snippets/README.md`

## Protocol matrix

| Scenario | Runtime requirement | Purpose |
|---|---|---|
| `protocol/create-intent` | none | Intent payload/contract baseline |
| `protocol/minimal-axp-service` | none | Minimal AXP-compatible lifecycle service |
| `protocol/conformance-runner` | none | Validate custom implementation with conformance |
