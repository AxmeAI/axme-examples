# Landing Example: Approval Flow

Use this as the primary landing-page code block. It shows the core AXME value in seconds:

`submit intent -> auto-approve -> COMPLETED`

Get API key on the landing page: <https://cloud.axme.ai/alpha>

Notes:

- In landing snippets, do not show `baseUrl`; SDK default points to AXME Cloud.
- `AXME_API_KEY` value is a service-account key (`axme_sa_...`) sent as `x-api-key`.

```ts
const client = new AxmeClient({ apiKey: process.env.AXME_API_KEY! });

const created = await client.createIntent({ intent_type: "intent.approval.demo.v1" });
await client.resumeIntent(created.intent_id, { approve_current_step: true });
await client.resolveIntent(created.intent_id, { status: "COMPLETED" });
```

```text
submit -> AUTO_APPROVED -> COMPLETED
```

Production note for landing copy:

AXME Cloud currently provides the runtime for executing intents. Public repositories include the protocol, SDKs, CLI, conformance tests, docs, and integration examples.
