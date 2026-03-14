# HTTP Binding Example

**Delivery mode:** `http` — AXME POSTs intents to your agent's `callback_url`. Managed delivery with retry and dead-letter tracking.

## What this example does

An order processor agent that accepts `order.placed` events via HTTP webhook:
- validates order fields (amount, currency, order_id)
- generates a tracking ID
- resumes the intent with COMPLETED or FAILED

## When to use HTTP binding

| Use http when... | Use stream when... |
|---|---|
| Your service is already an HTTP endpoint | You want native AXME integration |
| Migrating from webhooks | Starting fresh |
| AXME-managed retries needed | You manage reconnect yourself |
| Enterprise firewall, inbound only | Outbound SSE connection OK |

## Prerequisites

```bash
pip install axme
axme login
```

## Register the agent with callback_url

Before running the scenario, register the agent with its `callback_url`:

```bash
# Register (or update) the agent's callback URL
axme agents update http-order-processor --callback-url https://<your-url>/intent

# Or at registration time:
axme agents register --name http-order-processor \
    --delivery-mode http \
    --callback-url https://<your-url>/intent
```

## Run

**Step 1 — Start the agent:**

```bash
export AXME_API_KEY=$(axme agents keys show http-order-processor)
export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/http-order-processor
export AXME_BASE_URL=https://api.cloud.axme.ai
export CALLBACK_URL=https://<your-public-url>/intent
export PORT=8080

python agent.py
```

For local development, expose the port via ngrok:

```bash
ngrok http 8080
# copy the https URL and set CALLBACK_URL=https://<id>.ngrok.io/intent
```

**Step 2 — Submit the scenario:**

```bash
axme scenarios apply scenario.json --watch
```

## How it works

```
axme scenarios apply
    └── provisions http-order-processor (if needed)
    └── POST /v1/scenarios/apply  →  intent created
                                          │
                                          ▼  AXME POSTs to callback_url
                               agent.py  POST /intent
                                   ├── respond 200 immediately (ACK)
                                   ├── process in background thread
                                   │     ├── get_intent(id)
                                   │     ├── _process_order(payload)
                                   │     └── resume_intent(id, result)
                                          │
                                          ▼
                                   --watch shows COMPLETED / FAILED
```

## AXME retry behavior

If your agent returns a non-2xx response (or times out), AXME will retry up to `max_delivery_attempts` times (configured in `scenario.json`). After exhausting retries, the intent transitions to `FAILED` with `intent.delivery_failed` event.

## Security (HMAC signature)

AXME signs every delivery with `X-Axme-Signature: sha256=<hmac>`. To enable verification:

```bash
export AXME_WEBHOOK_SECRET=<your-secret>
# Configure the same secret in AXME when registering the agent (Block 9 — coming soon)
```

Without `AXME_WEBHOOK_SECRET`, the agent processes all deliveries (development mode).
