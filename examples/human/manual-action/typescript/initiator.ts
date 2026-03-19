/**
 * Manual action — human/manual-action example (TypeScript).
 *
 * Creates an intent with a human manual-action step. The workflow pauses
 * and emails the technician a link to report on a physical rack inspection.
 *
 * Run:
 *   AXME_API_KEY=<key> npx tsx initiator.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });

console.log("creating manual-action intent ...");
const intentId = await client.sendIntent({
  intent_type: "intent.dc.manual_action.v1",
  from_agent: "initiator://human-manual-action",
  to_agent: "agent://agent_core",
  payload: {
    rack_id: "B-14",
    location: "DC-East",
    alert: "elevated_temperature",
  },
  human_task: {
    title: "Inspect server rack B-14",
    description: "Elevated temperature alert in rack B-14 at DC-East. Please physically inspect the rack, check airflow and cooling, and report findings with evidence.",
    task_type: "manual_action",
    notify_email: process.env.AXME_NOTIFY_EMAIL ?? "dc-ops@example.com",
    allowed_outcomes: ["completed", "failed"],
    evidence_required: true,
  },
});
console.log(`intent created: ${intentId}`);
console.log("Check your email for the task link.");
