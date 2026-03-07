# Example Catalog

Use-case-first canonical **Cloud runtime** examples:

1. `approval-workflow`
2. `external-callback`
3. `retry-workflow`
4. `multi-service-coordination`

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
