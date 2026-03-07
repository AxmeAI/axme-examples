# Retry Workflow

Problem: transient dependency failures should not lose operation state.  
Goal: run retry with backoff while preserving one intent and one durable lifecycle.

This example demonstrates:

- idempotent intent creation
- retry loop with exponential backoff
- optional control updates between attempts
- terminal completion after successful retry

## Requirements

This example runs against **AXME Cloud**.

You need:

- AXME Cloud API key (generated on the landing page)
- `.env` file with `AXME_API_KEY` set (copy from `.env.example`)
- optional `AXME_BASE_URL` override (defaults to AXME Cloud endpoint)

Get API key at:

- <https://cloud.axme.ai/alpha>

```mermaid
sequenceDiagram
    participant App as Client App
    participant AXME as AXME Cloud Runtime
    participant Dep as External Dependency

    App->>AXME: create intent (idempotency key)
    loop Retry attempts
        App->>Dep: execute step
        Dep-->>App: transient failure
        App->>AXME: update controls / keep lifecycle context
    end
    App->>Dep: execute step (success)
    Dep-->>App: success payload
    App->>AXME: resolve COMPLETED
```

## Run (Python)

```bash
cd examples/retry-workflow/python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
# edit ../.env and set AXME_API_KEY
# optional override:
# export AXME_BASE_URL="https://api.cloud.axme.ai"
python main.py
```

## Run (TypeScript)

```bash
cd examples/retry-workflow/typescript
npm install
cp ../.env.example ../.env
# edit ../.env and set AXME_API_KEY
# optional override:
# export AXME_BASE_URL="https://api.cloud.axme.ai"
npm run start
```

Built using AXME (AXP).
