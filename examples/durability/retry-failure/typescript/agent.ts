/**
 * Webhook Receiver Agent — durability/retry-failure example (TypeScript).
 *
 * Processes webhook events idempotently. Run WITHOUT the agent to observe
 * AXME's retry-then-fail behavior.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=webhook-receiver-agent
 *   npx tsx examples/durability/retry-failure/agent.ts
 */
import { createHash } from "node:crypto";
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "webhook-receiver-agent";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

function processWebhook(payload: Record<string, unknown>): Record<string, unknown> {
  const eventType = String(payload.event_type ?? "unknown");
  const source = String(payload.source ?? "");
  const testId = String(payload.test_id ?? "");
  const fingerprint = createHash("sha256").update(`${eventType}:${source}:${testId}`).digest("hex").slice(0, 16);
  return { event_type: eventType, source, fingerprint, processed: true, note: `webhook event '${eventType}' processed from '${source}'` };
}

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
console.log(`webhook-receiver starting  address=${AXME_AGENT_ADDRESS}  binding=stream`);

try {
  for await (const delivery of client.listen(AXME_AGENT_ADDRESS)) {
    const intentId = String(delivery.intent_id ?? "");
    if (!intentId) continue;
    console.log(`received intent ${intentId}`);

    let intent: Record<string, unknown>;
    try {
      const resp = await client.getIntent(intentId);
      intent = (resp.intent ?? resp) as Record<string, unknown>;
    } catch (e) { console.error(`get_intent(${intentId}) failed:`, e); continue; }

    const status = String(intent.lifecycle_status ?? intent.status ?? "").toUpperCase();
    if (!["CREATED", "DELIVERED", "ACKNOWLEDGED", "IN_PROGRESS", "WAITING"].includes(status)) continue;

    const rawPayload = (intent.payload ?? {}) as Record<string, unknown>;
    const effectivePayload = (rawPayload.parent_payload ?? rawPayload) as Record<string, unknown>;
    const result = processWebhook(effectivePayload);

    console.log(`processed webhook for ${intentId}: fingerprint=${result.fingerprint}`);

    try {
      await client.resumeIntent(intentId, { action: "complete", ...result }, { ownerAgent: AXME_AGENT_ADDRESS });
      console.log(`resumed intent ${intentId}`);
    } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
