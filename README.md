# AXME Examples

Production-ready examples for the AXME platform — all delivery bindings, human approval flows, internal runtime, durability scenarios, and multi-agent orchestration.

Each example is available in **5 languages**: Python, TypeScript, Go, Java, .NET.

## Quick Start

```bash
# 1. Install the CLI + SDK
pip install axme

# 2. Log in
export AXME_CLI_SECRET_STORAGE=file
axme login

# 3. Run any scenario (provisions agents, sends intent, watches lifecycle)
axme scenarios apply examples/delivery/stream/scenario.json --watch
```

## Repository Structure

```
axme-examples/
├── examples/
│   ├── delivery/
│   │   ├── stream/              # SSE persistent connection
│   │   ├── poll/                # Periodic polling
│   │   ├── http/                # AXME pushes to callback URL
│   │   └── inbox/               # reply_to inbox pattern
│   ├── human/
│   │   ├── cli/                 # CLI approval (axme tasks approve)
│   │   ├── email/               # Email magic link approval
│   │   └── form/                # Structured form approval
│   ├── internal/
│   │   ├── delay/               # Step deadline enforcement
│   │   ├── notification/        # Owner notification + ack
│   │   ├── escalation/          # Reminder chain + escalation
│   │   ├── human_approval/      # Pure human gate (scenario-only)
│   │   ├── timeout/             # Timeout demo (scenario-only)
│   │   └── reminder/            # Reminder demo (scenario-only)
│   ├── durability/
│   │   ├── retry-failure/       # Delivery retry exhaustion → FAILED
│   │   ├── timeout/             # Step deadline → TIMED_OUT
│   │   └── reminder-escalation/ # Human SLA → reminders → escalation
│   ├── full/
│   │   ├── multi-agent/         # 2 agents + human approval in one workflow
│   │   └── multi-binding/       # SSE + HTTP in one workflow (scenario-only)
│   └── model-a/
│       ├── simple-request/      # Initiator waits for agent response
│       ├── fire-and-forget/     # Send intent, disconnect, check later
│       └── manual-multi-step/   # Chain 2 agents sequentially
├── protocol/                    # AXP protocol-only examples (runtime-agnostic)
├── runner/                      # Python handler library (used by axme CLI)
├── tests/                       # Unit tests for handlers
├── lang/                        # Language-specific build configs
│   ├── typescript/              # package.json, tsconfig.json
│   ├── java/                    # pom.xml, SseHelper.java
│   └── dotnet/                  # AxmeExamples.csproj, SseHelper.cs
└── docs/                        # Supporting documentation
```

## Per-Example Layout

Each example contains a shared `scenario.json` and language-specific implementations:

```
examples/delivery/stream/
├── scenario.json            # Shared across all languages
├── README.md
├── python/agent.py          # Python (pip install axme)
├── typescript/agent.ts      # TypeScript (npx tsx)
├── go/agent.go              # Go (go run)
├── java/StreamAgent.java    # Java (Maven)
└── dotnet/StreamAgent.cs    # .NET (dotnet run)
```

## Running Examples

### Model B — ScenarioBundle (recommended)

Most examples use `scenario.json` + the AXME CLI:

```bash
# Step 1: Provision agents + submit intent + watch lifecycle
axme scenarios apply examples/delivery/stream/scenario.json --watch

# Step 2: Start the agent in a separate terminal
# Python:
AXME_API_KEY=<agent-key> python examples/delivery/stream/python/agent.py

# TypeScript:
AXME_API_KEY=<agent-key> npx tsx examples/delivery/stream/typescript/agent.ts

# Go:
AXME_API_KEY=<agent-key> go run examples/delivery/stream/go/agent.go

# Java (from repo root):
cd lang/java && mvn -q compile exec:java \
  -Dexec.mainClass=ai.axme.examples.delivery.StreamAgent

# .NET (from repo root):
cd lang/dotnet && dotnet run -p:ExampleClass=AxmeExamples.Delivery.StreamAgent
```

### Model A — Direct API (no ScenarioBundle)

Model A examples use the SDK directly — the initiator creates intents via API:

```bash
# Start agent
AXME_API_KEY=<agent-key> python examples/delivery/stream/python/agent.py

# Run initiator
AXME_API_KEY=<workspace-key> \
AXME_TO_AGENT=agent://org/workspace/compliance-checker-agent \
  python examples/model-a/simple-request/python/initiator.py
```

## Examples

### Delivery Bindings

| Example | Pattern | Agent needed? |
|---------|---------|:------------:|
| `delivery/stream` | SSE persistent connection — real-time delivery | Yes |
| `delivery/poll` | Periodic polling — batch/serverless friendly | Yes |
| `delivery/http` | AXME POSTs to agent's callback URL | Yes (HTTP server) |
| `delivery/inbox` | reply_to inbox — disconnect-safe | Yes |

### Human Approval

| Example | Approval method |
|---------|----------------|
| `human/cli` | `axme tasks approve <id>` from terminal |
| `human/email` | One-click magic link in email |
| `human/form` | Structured form with required fields |

### Internal Runtime

| Example | What it demonstrates |
|---------|---------------------|
| `internal/delay` | Step deadline (120s) — agent must respond in time |
| `internal/notification` | Built-in notification to service owner |
| `internal/escalation` | Reminders + timeout escalation chain |
| `internal/human_approval` | Pure human gate, no agent (scenario-only) |
| `internal/timeout` | Step timeout demo (scenario-only) |
| `internal/reminder` | Reminder email demo (scenario-only) |

### Durability

| Example | What it demonstrates |
|---------|---------------------|
| `durability/retry-failure` | Delivery retry exhaustion → FAILED |
| `durability/timeout` | Step deadline → TIMED_OUT |
| `durability/reminder-escalation` | Human SLA breach → reminders → escalation |

### Full Workflows

| Example | What it demonstrates |
|---------|---------------------|
| `full/multi-agent` | Compliance check → risk assessment → CAB human approval |
| `full/multi-binding` | SSE + HTTP push in one workflow (scenario-only) |

### Model A (Manual Lifecycle)

| Example | Pattern |
|---------|---------|
| `model-a/simple-request` | Create intent → observe → wait for completion |
| `model-a/fire-and-forget` | Create intent → disconnect → check status later |
| `model-a/manual-multi-step` | Chain 2 agents sequentially via initiator code |

## SDK Versions

All examples use AXME SDK v0.1.2:

| Language | Package | Install |
|----------|---------|---------|
| Python | `axme` | `pip install axme` |
| TypeScript | `@axme/axme` | `npm install @axme/axme` |
| Go | `axme-sdk-go` | `go get github.com/AxmeAI/axme-sdk-go@v0.1.2` |
| Java | `ai.axme:axme` | Maven Central |
| .NET | `Axme` | `dotnet add package Axme` |

## Environment Variables

| Variable | Required | Description |
|----------|:--------:|-------------|
| `AXME_API_KEY` | Yes | Service account or workspace API key |
| `AXME_BASE_URL` | No | Default: `https://api.cloud.axme.ai` |
| `AXME_AGENT_ADDRESS` | No | Agent address (bare name or full `agent://...`) |

## Alpha Access

Install the CLI and log in: `curl -fsSL https://raw.githubusercontent.com/AxmeAI/axme-cli/main/install.sh | sh && axme login`
Contact: hello@axme.ai
