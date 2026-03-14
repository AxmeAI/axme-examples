# Poll Binding Example

**Delivery mode:** `poll` — agent periodically reconnects to check for new intents, no persistent connection.

## What this example does

A batch-processor agent receives batch specifications and validates/processes them:
- validates `record_type` against supported types
- validates required fields (`batch_id`, `date_range`)
- returns computed record counts per type

## When to use poll over stream

| Use poll when... | Use stream when... |
|---|---|
| Running as a cron job | Realtime processing needed |
| Serverless / Lambda | Persistent process |
| Controlled poll interval | Immediate push delivery |
| Behind firewall, no inbound | Any persistent outbound OK |

## Prerequisites

```bash
pip install axme python-dotenv
axme login
```

## Run

**Step 1 — Start the agent:**

```bash
export AXME_API_KEY=$(axme agents keys show batch-processor-agent)
export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/batch-processor-agent
export AXME_BASE_URL=https://api.cloud.axme.ai
export POLL_INTERVAL=10   # seconds between polls

python agent.py
```

**Step 2 — Submit the scenario:**

```bash
axme scenarios apply scenario.json --watch
```

The intent will be delivered on the agent's next poll cycle (within `POLL_INTERVAL` seconds).

## How it works

```
axme scenarios apply
    └── provisions batch-processor-agent (if needed)
    └── POST /v1/scenarios/apply  →  intent created, waits for poll
                                          │
                                   (up to POLL_INTERVAL seconds later)
                                          ▼
                               batch-processor-agent wakes up
                                   ├── connect to AXME (5s timeout)
                                   ├── drain new intents
                                   ├── get_intent(id)
                                   ├── _process_batch(payload)
                                   ├── resume_intent(id, {action: complete/fail})
                                   └── disconnect, sleep POLL_INTERVAL
                                          │
                                          ▼
                                   --watch shows COMPLETED / FAILED
```

## Poll cursor

The agent tracks a `_CURSOR` (sequence number) to avoid re-processing intents across cycles. In production, persist this cursor to a file or database so it survives restarts.
