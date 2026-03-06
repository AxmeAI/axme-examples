# axme-examples Content Roadmap (Alpha)

This roadmap defines what must be implemented before `axme-examples` can claim full README maturity.

## Adoption-Driven Targets

Derived from `axme-local-internal/plans/ADOPTION_PRIMARY_ACTIONS_EXECUTION_PLAN.md`:

- At least 3 runnable Tier-1 framework examples in this repository.
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

- Create `examples/` subfolders for selected Tier-1 targets.
- Add shared helper scripts (`scripts/validate_examples.sh`).
- Replace README-only smoke CI with runnable validation jobs.

### Phase B - Tier-1 initial delivery

Implement at least three:

- `examples/langgraph-distributed-agents`
- `examples/autogen-cross-machine-handoff`
- `examples/openai-agents-handoff-bridge`

### Phase C - Docs and discoverability

- Add `docs/example-matrix.md` with use-case and support status.
- Tag repository with backend + agent-discovery topics.
- Link examples from `axme-docs` integration quickstart pages.

## Definition of Ready for Full README

Full README overhaul is unlocked only when:

1. Three runnable examples are merged.
2. CI executes example flows on PR.
3. Example matrix is published.
4. Alpha disclaimer and usage limits are consistently documented.
