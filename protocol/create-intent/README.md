# Protocol Example: Create Intent

Goal: show the minimal AXP-style intent envelope and protocol-level submission flow.

This example is runtime-agnostic. It does not depend on AXME Cloud orchestration features.

## Minimal payload shape

```json
{
  "intent_type": "demo.intent.v1",
  "correlation_id": "3f1680f7-64bb-4a74-a8b4-bf5bc6a8ad84",
  "from_agent": "agent://source",
  "to_agent": "agent://target",
  "payload": {
    "task": "demo"
  }
}
```

Files in this folder:

- `intent.json` - baseline payload
- `send_with_curl.sh` - simple protocol submission helper

## Protocol check goals

- valid required fields
- stable idempotency key on retries
- deterministic response contract from receiver

## Next step

Use `../minimal-axp-service` for a tiny service that accepts and resolves intents.
