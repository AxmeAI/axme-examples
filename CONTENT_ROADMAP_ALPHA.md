# axme-examples Content Roadmap (Alpha)

This roadmap defines what must be implemented before `axme-examples` can claim full README maturity.

## Adoption-Driven Targets

Derived from `axme-local-internal/plans/ADOPTION_PRIMARY_ACTIONS_EXECUTION_PLAN.md`:

- 4 runnable canonical developer-infra examples in this repository:
  - `examples/approval-workflow`
  - `examples/external-callback`
  - `examples/retry-workflow`
  - `examples/multi-service-coordination`
- Protocol-only examples for open ecosystem path:
  - `protocol/create-intent`
  - `protocol/minimal-axp-service`
  - `protocol/conformance-runner`
- One-command run path per example.
- Problem-first README opening (first 5 lines).
- Explicit Alpha disclaimer in all example READMEs.
- CI that executes examples (not smoke-only file checks).

## Mandatory Example Baseline (Each Example)

- Source code and dependency manifest committed.
- `.env.example` present.
- `run` command and expected output documented.
- Failure/retry behavior documented.
- Attribution footer: `Built using AXME (AXP)`.

## Phase Plan

### Phase A - Repository skeleton

- Create `examples/` subfolders by canonical use-case.
- Add shared helper scripts (`scripts/validate_examples.sh`).
- Replace README-only smoke CI with runnable validation jobs.

### Phase B - Canonical core delivery

Implement all four:

- `examples/approval-workflow`
- `examples/external-callback`
- `examples/retry-workflow`
- `examples/multi-service-coordination`

Language support policy:

- Full runnable flows: Python + TypeScript.
- Go/Java/.NET: snippets-only lane under `snippets/`.

### Phase C - Docs and discoverability

- Add `docs/example-matrix.md` with use-case and support status.
- Tag repository with backend + agent-discovery topics.
- Link examples from `axme-docs` integration quickstart pages.
- Keep cloud/protocol split explicit in README and docs.

## Definition of Ready for Full README

Full README overhaul is unlocked only when:

1. Three runnable examples are merged.
2. CI executes example flows on PR.
3. Example matrix is published.
4. Alpha disclaimer and usage limits are consistently documented.
