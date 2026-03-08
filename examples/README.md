# Example Catalog

Use-case-first canonical **Cloud runtime** examples:

1. `approval-workflow` — single-actor auto-approval path
2. `external-callback` — waiting for an external callback
3. `retry-workflow` — automatic retry with backoff
4. `multi-service-coordination` — parallel child intents
5. `multi-actor-approval` — two distinct actors (requester + approver), each with their own `actor_token`

Each scenario includes:

- `.env.example`
- `README.md`
- `python/` runnable flow
- `typescript/` runnable flow

All examples in this directory run against **AXME Cloud** and require an API key from the landing page.
Get API key: <https://cloud.axme.ai/alpha>

Environment model:

- `AXME_API_KEY` - required
- `AXME_BASE_URL` - optional; defaults to AXME Cloud endpoint

For protocol-only examples without AXME Cloud runtime, see [`../protocol/README.md`](../protocol/README.md).
For Go/Java/.NET usage snippets, see [`../snippets/README.md`](../snippets/README.md).
