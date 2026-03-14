# Inbox / Reply-to Binding Example

**Delivery mode:** `inbox` (reply_to pattern) — disconnect-safe result delivery to the initiator's inbox.

## What this example does

Demonstrates the disconnect-safe pattern:
1. Initiator submits an order intent with `reply_to = initiator inbox address`
2. Fulfillment agent (stream binding) receives, processes, resumes
3. AXME delivers the result to the initiator's inbox
4. Initiator reads the result at any time, independently

The fulfillment agent validates orders and generates tracking numbers.

## When to use inbox/reply_to

| Use inbox/reply_to when... | Use stream when... |
|---|---|
| Initiator may disconnect | Initiator stays connected |
| Async workflow, result later | Synchronous wait for result |
| Mobile app / short-lived client | Long-running process |
| Fire-and-forget with result pickup | Need immediate confirmation |

## Two roles, two scripts

| File | Role | Description |
|---|---|---|
| `agent.py` | **Processor** (fulfillment-service-agent) | Stream agent that processes orders |
| `check_inbox.py` | **Initiator reader** | Reads fulfillment result from inbox |

## Prerequisites

```bash
pip install axme
axme login
```

## Run

**Step 1 — Start the fulfillment agent (processor side):**

```bash
export AXME_API_KEY=$(axme agents keys show fulfillment-service-agent)
export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/fulfillment-service-agent
export AXME_BASE_URL=https://api.cloud.axme.ai

python agent.py
```

**Step 2 — Submit the scenario** (in another terminal):

```bash
axme scenarios apply scenario.json --watch
```

`--watch` streams events until COMPLETED. Once done, the result is in the initiator's inbox.

**Step 3 — Read the result from inbox** (initiator side):

```bash
export AXME_API_KEY=<initiator-api-key>

python check_inbox.py
# or via CLI:
axme inbox list
```

## How it works

```
axme scenarios apply --watch
    └── provisions fulfillment-service-agent (if needed)
    └── POST /v1/scenarios/apply
        └── intent created with reply_to=initiator_inbox
                │
                ▼  AXME pushes via SSE
     fulfillment-service-agent (agent.py)
         ├── get_intent(id)
         ├── _fulfill_order(payload) → tracking number, eta
         └── resume_intent(id, {action: complete, ...})
                │
                ▼  AXME delivers result to reply_to inbox
          initiator inbox  (read by check_inbox.py)
                │
                ▼
         --watch shows COMPLETED  ✓
```

## The reply_to field

In `scenario.json`, `"reply_to": "initiator_inbox"` is a symbolic reference.
The CLI (`axme scenarios apply`) substitutes it with the actual initiator's inbox address when submitting.

In a real application, you'd set:
```python
client.create_intent({
    ...,
    "reply_to": "agent://my-org/my-ws/my-inbox",
})
```
