/**
 * Model A — Simple Request: initiator waits for agent response (TypeScript).
 *
 * Run:
 *   # Terminal 1 — start the agent
 *   AXME_API_KEY=<agent-key> npx tsx examples/delivery/stream/agent.ts
 *
 *   # Terminal 2 — run the initiator
 *   AXME_API_KEY=<workspace-key> AXME_TO_AGENT=agent://org/ws/compliance-checker-agent \
 *     npx tsx examples/model-a/simple-request/initiator.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_TO_AGENT = process.env.AXME_TO_AGENT ?? "";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required (workspace API key)"); process.exit(1); }
if (!AXME_TO_AGENT) { console.error("AXME_TO_AGENT is required (e.g. agent://org/workspace/compliance-checker-agent)"); process.exit(1); }

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });

// 1. Create intent
console.log(`creating intent to ${AXME_TO_AGENT} ...`);
const intentId = await client.sendIntent({
  intent_type: "intent.compliance.check.v1",
  from_agent: "initiator://simple-request",
  to_agent: AXME_TO_AGENT,
  payload: {
    change_id: "CHG-MODEL-A-001", service: "api-gateway", version: "4.0.0",
    environment: "staging", change_type: "config_update", risk_level: "low",
  },
});
console.log(`intent created: ${intentId}`);

// 2. Wait for agent to process
console.log("waiting for agent response...");
for await (const event of client.observe(intentId, { timeoutMs: 120_000 })) {
  const status = String(event.status ?? "");
  if (["COMPLETED", "IN_PROGRESS", "FAILED", "CANCELED", "TIMED_OUT"].includes(status)) {
    console.log(`intent ${intentId} → ${status}`);
    if (["COMPLETED", "IN_PROGRESS"].includes(status)) console.log("SUCCESS — agent processed the request");
    else console.warn(`intent ended with status: ${status}`);
    break;
  }
}
