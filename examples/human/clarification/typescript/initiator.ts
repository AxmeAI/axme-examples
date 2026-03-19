/**
 * Clarification — human/clarification example (TypeScript).
 *
 * Creates an intent with a human clarification step. The workflow pauses
 * and emails the assignee a link to provide missing information or decline.
 *
 * Run:
 *   AXME_API_KEY=<key> npx tsx initiator.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });

console.log("creating clarification intent ...");
const intentId = await client.sendIntent({
  intent_type: "intent.customer.clarification.v1",
  from_agent: "initiator://human-clarification",
  to_agent: "agent://agent_core",
  payload: {
    customer: "ABC Corp",
    ticket: "ONBOARD-429",
  },
  human_task: {
    title: "Clarification needed \u2014 ABC Corp onboarding",
    description: "Ticket ONBOARD-429 for ABC Corp requires additional information before onboarding can proceed. Please provide the requested details or decline.",
    task_type: "clarification",
    notify_email: process.env.AXME_NOTIFY_EMAIL ?? "cs@example.com",
    allowed_outcomes: ["provided", "declined"],
    required_comment: true,
  },
});
console.log(`intent created: ${intentId}`);
console.log("Check your email for the task link.");
