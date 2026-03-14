# Stream Binding Example

**Delivery mode:** `stream` — agent holds a persistent SSE connection, AXME pushes intents immediately.

## What this example does

A compliance-checker agent receives change requests and validates them against real business rules:
- production environment → blocked (requires manual approval)
- high/critical risk without backup → blocked
- all other cases → approved with details

## Prerequisites

```bash
pip install axme python-dotenv
axme login
```

## Run

**Step 1 — Start the agent** (acts as your deployed service):

```bash
export AXME_API_KEY=$(axme agents keys show compliance-checker-agent)
export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/compliance-checker-agent
export AXME_BASE_URL=https://api.cloud.axme.ai

python agent.py
```

**Step 2 — Submit the scenario** (in another terminal):

```bash
axme scenarios apply scenario.json --watch
```

The `--watch` flag streams real-time intent lifecycle events to the terminal.

## How it works

```
axme scenarios apply
    └── provisions compliance-checker-agent (if needed)
    └── POST /v1/scenarios/apply  →  intent created
                                          │
                                          ▼  AXME pushes over open SSE
                               compliance-checker-agent (agent.py)
                                   ├── get_intent(id)
                                   ├── run compliance rules
                                   └── resume_intent(id, {action: complete/fail})
                                          │
                                          ▼
                                   --watch shows COMPLETED / FAILED
```

## Modify for your use case

1. Replace the `_check_compliance()` function with your business rules.
2. Change `AXME_AGENT_ADDRESS` to match your registered agent.
3. Update `scenario.json` with your intent type and payload.

## Delivery binding characteristics

| Property | Value |
|---|---|
| Connection | Persistent SSE (long-lived HTTP GET) |
| Latency | Immediate push, ~100ms |
| Reconnect | Automatic (SDK handles with cursor) |
| Best for | Real-time processing, event-driven agents |
