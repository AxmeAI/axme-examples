/**
 * Model A — Fire and Forget: send intent, disconnect, check later (TypeScript).
 *
 * Run:
 *   AXME_API_KEY=<workspace-key> AXME_TO_AGENT=agent://org/ws/compliance-checker-agent \
 *     npx tsx examples/model-a/fire-and-forget/initiator.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_TO_AGENT = process.env.AXME_TO_AGENT ?? "";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }
if (!AXME_TO_AGENT) { console.error("AXME_TO_AGENT is required"); process.exit(1); }

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });

// 1. Fire
console.log(`firing intent to ${AXME_TO_AGENT} ...`);
const intentId = await client.sendIntent({
  intent_type: "intent.compliance.check.v1",
  from_agent: "initiator://fire-and-forget",
  to_agent: AXME_TO_AGENT,
  reply_to: "initiator://fire-and-forget",
  payload: {
    change_id: "CHG-FIRE-FORGET-001", service: "payments-service", version: "2.1.0",
    environment: "staging", change_type: "config_update", risk_level: "medium",
  },
});
console.log(`intent sent: ${intentId} — disconnecting`);

// 2. Forget — do other work
console.log("doing other work for 15 seconds...");
await new Promise(r => setTimeout(r, 15_000));

// 3. Check result
console.log("checking intent status...");
const resp = await client.getIntent(intentId);
const intentData = (resp.intent ?? resp) as Record<string, unknown>;
const finalStatus = String(intentData.lifecycle_status ?? intentData.status ?? "?");
console.log(`intent ${intentId} → ${finalStatus}`);

if (["COMPLETED", "IN_PROGRESS"].includes(finalStatus)) {
  console.log("SUCCESS — fire-and-forget pattern verified");
} else {
  console.log(`status: ${finalStatus} (agent may still be processing)`);
}
