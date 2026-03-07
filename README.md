# axme-examples

Reference, runnable AXME examples organized by **use case**, not by language.

> **Alpha**: APIs and behavior are still evolving.  
> Get API key: <https://cloud.axme.ai/alpha> · Contact: [hello@axme.ai](mailto:hello@axme.ai)

## Runtime Model

AXME Cloud currently provides the runtime environment for executing intents.

Publicly available:

- AXP spec and schemas
- SDKs
- CLI
- conformance tests
- docs
- integration examples

Managed/closed:

- AXME Cloud runtime
- Registry
- control plane
- production execution infrastructure

## Example Families

This repository is split into two families:

- **Cloud examples** (`cloud/` + `examples/`)  
  Runnable end-to-end scenarios that use AXME Cloud runtime.
- **Protocol examples** (`protocol/`)  
  AXP-only examples that do not require AXME Cloud runtime.

Cloud examples are the product path; protocol examples are for teams implementing or validating AXP-compatible components.

## Requirements

These examples run against **AXME Cloud**.

You need:

- AXME Cloud API key in `AXME_API_KEY` (issued on the landing page)

Get API key at:

- <https://cloud.axme.ai/alpha>

Environment model:

- `AXME_API_KEY` - required; value is a workspace/service-account key (`axme_sa_...`) sent as `x-api-key`
- `AXME_BASE_URL` - optional override; defaults to `https://api.cloud.axme.ai`

## Auth Model For Examples

- Machine-to-machine examples in this repository use `AXME_API_KEY` only.
- No actor/session token is required for the canonical examples.
- Actor token (`Authorization: Bearer <access_token>`) is a separate user/session layer and is only needed for actor-scoped enterprise operations.

## Additional Keys For Bots/Processes

If you need one key per bot/process, create extra service accounts and keys (do not run onboarding again):

```bash
axme service-accounts create \
  --org-id "<org_id>" \
  --workspace-id "<workspace_id>" \
  --name "bot-processor-a" \
  --created-by-actor-id "<actor_id>"

axme service-accounts list --org-id "<org_id>" --workspace-id "<workspace_id>"

axme service-accounts keys create \
  --service-account-id "<sa_id>" \
  --created-by-actor-id "<actor_id>"
```

## Cloud Canonical Example Set

| Example | What it demonstrates | Python | TypeScript |
|---|---|---|---|
| `examples/approval-workflow` | Automatic approval fast path (immediate `resume`/completion) | ✅ | ✅ |
| `examples/external-callback` | External system callback resumes intent flow | ✅ | ✅ |
| `examples/retry-workflow` | Retry with backoff + idempotent intent create semantics | ✅ | ✅ |
| `examples/multi-service-coordination` | Coordinating multiple services under one lifecycle | ✅ | ✅ |

See cloud index: [`cloud/README.md`](cloud/README.md)

## Protocol Example Set (No Cloud Runtime Required)

- `protocol/create-intent` - intent envelope shape and protocol-level submission flow
- `protocol/minimal-axp-service` - minimal AXP-compatible service lifecycle (`accept -> progress -> complete`)
- `protocol/conformance-runner` - run conformance suite against custom implementation

See protocol index: [`protocol/README.md`](protocol/README.md)

## Repository Layout

```text
cloud/
  README.md
  approval-workflow/
  external-callback/
  retry-workflow/
  multi-service-coordination/
examples/
  approval-workflow/
    .env.example
    README.md
    python/
    typescript/
  external-callback/
  retry-workflow/
  multi-service-coordination/
protocol/
  create-intent/
  minimal-axp-service/
  conformance-runner/
snippets/
  README.md
```

## Quick Start

### Python

```bash
cd examples/approval-workflow/python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
# edit ../.env and set AXME_API_KEY
# optional override for staging/dev:
# export AXME_BASE_URL="https://api.cloud.axme.ai"
python main.py
```

### TypeScript

```bash
cd examples/approval-workflow/typescript
npm install
cp ../.env.example ../.env
# edit ../.env and set AXME_API_KEY
# optional override for staging/dev:
# export AXME_BASE_URL="https://api.cloud.axme.ai"
npm run start
```

## Related Repositories

| Repository | Role |
|---|---|
| [axme-docs](https://github.com/AxmeAI/axme-docs) | API and integration docs |
| [axme-sdk-python](https://github.com/AxmeAI/axme-sdk-python) | Python SDK used by examples |
| [axme-sdk-typescript](https://github.com/AxmeAI/axme-sdk-typescript) | TypeScript SDK used by examples |
| [axme-sdk-go](https://github.com/AxmeAI/axme-sdk-go) | Go SDK snippets |
| [axme-sdk-java](https://github.com/AxmeAI/axme-sdk-java) | Java SDK snippets |
| [axme-sdk-dotnet](https://github.com/AxmeAI/axme-sdk-dotnet) | .NET SDK snippets |

## Contributing

- Suggest a new scenario with `example-request` issue label.
- Keep examples use-case-first and runnable end-to-end.
- Keep Cloud and Protocol examples explicitly separated.
- Keep tracked files in English.
