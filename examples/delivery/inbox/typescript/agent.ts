/**
 * Fulfillment Service Agent — inbox/reply_to delivery binding (TypeScript).
 *
 * The agent processes orders via stream binding. When completed, AXME
 * puts the result into the initiator's inbox (reply_to pattern).
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=fulfillment-service-agent
 *   npx tsx examples/delivery/inbox/agent.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "fulfillment-service-agent";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

// --- Business logic ---
const SHIPPING_ESTIMATES: Record<string, string> = {
  express: "1-2 business days", standard: "3-5 business days", economy: "7-10 business days",
};

function fulfillOrder(payload: Record<string, unknown>): Record<string, unknown> {
  const orderId = String(payload.order_id ?? "");
  const customer = String(payload.customer_id ?? "");
  const items = (payload.items ?? []) as Array<Record<string, unknown>>;
  const shipping = String(payload.shipping ?? "standard");

  if (!orderId) return { action: "fail", reason: "order_id is required" };
  if (!items.length) return { action: "fail", reason: "items list is empty" };
  if (!(shipping in SHIPPING_ESTIMATES)) return { action: "fail", reason: `unknown shipping method='${shipping}'` };

  const totalItems = items.reduce((sum, i) => sum + (Number(i.quantity) || 0), 0);
  if (totalItems <= 0) return { action: "fail", reason: "total item quantity must be > 0" };

  const h = (s: string) => { let v = 0; for (let i = 0; i < s.length; i++) v = (Math.imul(31, v) + s.charCodeAt(i)) | 0; return Math.abs(v); };
  return {
    action: "complete",
    fulfillment_id: `FUL-${String(h(orderId + customer) % 100000).padStart(5, "0")}`,
    tracking_number: `AXME-${orderId.toUpperCase()}-${String(h(orderId) % 10000).padStart(4, "0")}`,
    warehouse: "WH-US-EAST-1", shipping_method: shipping, eta: SHIPPING_ESTIMATES[shipping],
    items_shipped: totalItems, status: "fulfilled",
  };
}

// --- Agent loop ---
const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
console.log(`fulfillment-service-agent starting  address=${AXME_AGENT_ADDRESS}  binding=stream`);

try {
  for await (const delivery of client.listen(AXME_AGENT_ADDRESS)) {
    const intentId = String(delivery.intent_id ?? "");
    if (!intentId) continue;
    console.log(`received order intent ${intentId}`);

    let intent: Record<string, unknown>;
    try { intent = await client.getIntent(intentId); } catch (e) { console.error(`get_intent(${intentId}) failed:`, e); continue; }

    const payload = (intent.payload ?? {}) as Record<string, unknown>;
    const result = fulfillOrder(payload);
    const action = result.action;
    delete result.action;

    try {
      await client.resumeIntent(intentId, { action, ...result }, { ownerAgent: AXME_AGENT_ADDRESS });
      console.log(`resumed ${intentId}  action=${action}`);
    } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
