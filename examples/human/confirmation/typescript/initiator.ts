/**
 * Confirmation — human/confirmation example (TypeScript).
 *
 * Creates an intent with a human confirmation step. The workflow pauses
 * and emails the assignee a link to confirm or deny DNS propagation.
 *
 * Run:
 *   AXME_API_KEY=<key> npx tsx initiator.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });

console.log("creating confirmation intent ...");
const intentId = await client.sendIntent({
  intent_type: "intent.dns.confirmation.v1",
  from_agent: "initiator://human-confirmation",
  to_agent: "agent://agent_core",
  payload: {
    domain: "api.example.com",
    record_type: "CNAME",
    new_value: "new-lb.example.com",
  },
  human_task: {
    title: "Confirm DNS propagation",
    description: "DNS change submitted: api.example.com CNAME -> new-lb.example.com. Please verify propagation is complete.",
    task_type: "confirmation",
    notify_email: process.env.AXME_NOTIFY_EMAIL ?? "ops@example.com",
    allowed_outcomes: ["confirmed", "denied"],
  },
});
console.log(`intent created: ${intentId}`);
console.log("Check your email for the task link.");
