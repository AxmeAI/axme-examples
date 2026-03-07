# Cloud Examples Index

These examples require AXME Cloud runtime and an API key.

Use this path for product onboarding and lifecycle orchestration scenarios:

- durable execution
- retries and backoff
- callbacks and multi-service coordination
- workflow controls and runtime lifecycle events

## Canonical runnable set

- `../examples/approval-workflow`
- `../examples/external-callback`
- `../examples/retry-workflow`
- `../examples/multi-service-coordination`

Cloud aliases (stable path layout, no code duplication):

- `approval-workflow/`
- `external-callback/`
- `retry-workflow/`
- `multi-service-coordination/`

## Requirements

- `AXME_API_KEY` (service-account key from `https://cloud.axme.ai/alpha`)
- optional `AXME_BASE_URL` override (default `https://api.cloud.axme.ai`)

For protocol-only examples that do not require AXME Cloud, see `../protocol/README.md`.
