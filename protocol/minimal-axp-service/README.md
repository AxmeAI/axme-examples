# Protocol Example: Minimal AXP Service

Goal: demonstrate a tiny AXP-compatible lifecycle implementation without AXME Cloud runtime.

## Expected flow

1. Receive intent payload (`POST /v1/intents`)
2. Return accepted state (`CREATED` or `SUBMITTED`)
3. Expose status endpoint (`GET /v1/intents/{id}`)
4. Emit terminal state (`COMPLETED` or `FAILED`)

Files in this folder:

- `minimal_service.py` - tiny FastAPI service implementing the lifecycle surface
- `requirements.txt` - dependencies for local run

## Contract focus

- lifecycle transitions are explicit and observable
- idempotency key replay returns deterministic response
- protocol fields remain schema-compatible

## Notes

This is intentionally minimal and does not include managed-runtime features such as durable retries, orchestration policies, or registry routing.
