/**
 * Review — human/review example (TypeScript).
 *
 * Creates an intent with a human review step. The workflow pauses
 * and emails the reviewer a link to approve, request changes, or reject a PR.
 *
 * Run:
 *   AXME_API_KEY=<key> npx tsx initiator.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });

console.log("creating review intent ...");
const intentId = await client.sendIntent({
  intent_type: "intent.code.review.v1",
  from_agent: "initiator://human-review",
  to_agent: "agent://agent_core",
  payload: {
    pr_number: 847,
    title: "Add retry logic to payment service",
    author: "alice",
  },
  human_task: {
    title: "Review PR #847",
    description: "PR #847 'Add retry logic to payment service' by alice is ready for review. Please approve, request changes, or reject.",
    task_type: "review",
    notify_email: process.env.AXME_NOTIFY_EMAIL ?? "reviewer@example.com",
    allowed_outcomes: ["approved", "changes_requested", "rejected"],
  },
});
console.log(`intent created: ${intentId}`);
console.log("Check your email for the task link.");
