/**
 * Budget Envelope Validator — human/email example (TypeScript).
 *
 * Validates budget requests against quarterly allocations before
 * routing to a human approver via email.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=budget-envelope-validator
 *   npx tsx examples/human/email/agent.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "budget-envelope-validator";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

// --- Business logic ---
const QUARTERLY_ENVELOPES: Record<string, number> = {
  cloud_infrastructure: 50_000, software_licenses: 20_000,
  contractor_services: 40_000, hardware: 15_000,
};

function validateBudget(payload: Record<string, unknown>): { withinEnvelope: boolean; reason: string; meta: Record<string, unknown> } {
  const budgetId = String(payload.budget_id ?? "?");
  const amount = Number(payload.amount ?? 0);
  const currency = String(payload.currency ?? "USD");
  const category = String(payload.category ?? "");

  const envelope = QUARTERLY_ENVELOPES[category];
  if (envelope === undefined) {
    return { withinEnvelope: false, reason: `${budgetId}: unknown category '${category}'; known: ${Object.keys(QUARTERLY_ENVELOPES).sort()}`, meta: {} };
  }
  if (amount > envelope) {
    return { withinEnvelope: false, reason: `${budgetId}: ${currency} ${amount.toLocaleString()} exceeds quarterly envelope of ${currency} ${envelope.toLocaleString()} for '${category}'`, meta: { envelope, overage: amount - envelope } };
  }

  const headroomPct = Math.round((envelope - amount) / envelope * 1000) / 10;
  return { withinEnvelope: true, reason: `${budgetId}: ${currency} ${amount.toLocaleString()} is within '${category}' envelope (${headroomPct}% headroom)`, meta: { envelope, headroom_pct: headroomPct } };
}

// --- Agent loop ---
const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
console.log(`budget-envelope-validator starting  address=${AXME_AGENT_ADDRESS}  binding=stream`);

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
    const { withinEnvelope, reason, meta } = validateBudget(effectivePayload);

    console.log(`budget validation for ${intentId}: ok=${withinEnvelope}  reason=${reason}`);

    try {
      if (withinEnvelope) {
        await client.resumeIntent(intentId, {
          action: "complete", within_envelope: true, reason,
          envelope: meta.envelope, headroom_pct: meta.headroom_pct,
        }, { ownerAgent: AXME_AGENT_ADDRESS });
      } else {
        await client.resumeIntent(intentId, {
          action: "fail", within_envelope: false, reason,
        }, { ownerAgent: AXME_AGENT_ADDRESS });
      }
      console.log(`resumed intent ${intentId} (within_envelope=${withinEnvelope})`);
    } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
