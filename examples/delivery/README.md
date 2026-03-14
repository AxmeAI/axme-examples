# Delivery Bindings — Examples

All four AXME delivery modes, each as a self-contained `agent.py` + `scenario.json`.

## Quickstart

```bash
axme login
axme scenarios apply <binding>/scenario.json --watch
```

Before running, start the corresponding `agent.py` with the right `AXME_API_KEY`.

## Bindings at a glance

| Binding | How it works | Agent | Best for |
|---|---|---|---|
| **stream** | Agent holds SSE connection, AXME pushes immediately | `stream/agent.py` | Realtime, event-driven |
| **poll** | Agent periodically reconnects to check for new intents | `poll/agent.py` | Batch jobs, cron, serverless |
| **http** | AXME POSTs to agent's `callback_url` (managed delivery) | `http/agent.py` | Webhooks, enterprise HTTP |
| **inbox** | Result delivered to initiator's inbox after completion | `inbox/agent.py` | Disconnect-safe, async |

## Structure

```
delivery/
├── stream/
│   ├── agent.py        ← compliance checker agent (stream)
│   ├── scenario.json   ← submit with: axme scenarios apply stream/scenario.json --watch
│   └── README.md
├── poll/
│   ├── agent.py        ← batch processor agent (poll)
│   ├── scenario.json
│   └── README.md
├── http/
│   ├── agent.py        ← order processor agent (http webhook receiver)
│   ├── scenario.json
│   └── README.md
└── inbox/
    ├── agent.py        ← fulfillment service agent (stream, result → inbox)
    ├── check_inbox.py  ← initiator reads result from inbox
    ├── scenario.json
    └── README.md
```

## Requirements

```bash
pip install axme>=0.1.1 python-dotenv>=1.0.1
```

## Pattern: agent.py is a template

Each `agent.py` is a **standalone service** — deploy it anywhere (Cloud Run, EC2, Lambda, bare metal).
It connects to AXME using the SDK and processes incoming intents.

```
You write:         agent.py  — your business logic + AXME SDK
You define:        scenario.json  — what to run
AXME handles:      routing, delivery, retry, durability, events
You run:           axme scenarios apply scenario.json --watch
```

The `scenario.json` drives everything. The agent just needs to be running and connected.

## Environment variables (all agents)

| Variable | Required | Description |
|---|---|---|
| `AXME_API_KEY` | Yes | Agent's API key (`axme agents keys show <name>`) |
| `AXME_AGENT_ADDRESS` | Yes | `agent://<org>/<workspace>/<name>` |
| `AXME_BASE_URL` | No | Gateway URL (default: production) |

## Verify results via CLI

```bash
axme intents get <intent_id>
axme intents events <intent_id>
axme agents list
axme quota show
```
