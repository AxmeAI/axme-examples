/**
 * Override — human/override example (TypeScript).
 *
 * Creates an intent with a human override step. The workflow pauses
 * and emails the senior operator a link to approve or reject a deployment
 * freeze override with justification.
 *
 * Run:
 *   AXME_API_KEY=<key> npx tsx initiator.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });

console.log("creating override intent ...");
const intentId = await client.sendIntent({
  intent_type: "intent.deploy.override.v1",
  from_agent: "initiator://human-override",
  to_agent: "agent://agent_core",
  payload: {
    service: "api-gateway",
    version: "v3.5.0",
    ticket: "CHG-2026-892",
  },
  human_task: {
    title: "Override deployment freeze",
    description: "Deployment of api-gateway v3.5.0 is blocked by a deployment freeze (ticket CHG-2026-892). A senior operator must approve the override with justification or reject.",
    task_type: "override",
    notify_email: process.env.AXME_NOTIFY_EMAIL ?? "senior-ops@example.com",
    allowed_outcomes: ["override_approved", "rejected"],
    required_comment: true,
  },
});
console.log(`intent created: ${intentId}`);
console.log("Check your email for the task link.");
