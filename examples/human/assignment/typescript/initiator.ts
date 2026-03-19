/**
 * Assignment — human/assignment example (TypeScript).
 *
 * Creates an intent with a human assignment step. The workflow pauses
 * and emails the on-call manager a link to assign an incident commander.
 *
 * Run:
 *   AXME_API_KEY=<key> npx tsx initiator.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });

console.log("creating assignment intent ...");
const intentId = await client.sendIntent({
  intent_type: "intent.incident.assignment.v1",
  from_agent: "initiator://human-assignment",
  to_agent: "agent://agent_core",
  payload: {
    incident_id: "INC-2026-1847",
    severity: "P1",
    service: "payment-api",
  },
  human_task: {
    title: "Assign incident commander",
    description: "Incident INC-2026-1847 classified as P1 affecting payment-api. Please designate an incident commander.",
    task_type: "assignment",
    notify_email: process.env.AXME_NOTIFY_EMAIL ?? "oncall@example.com",
    allowed_outcomes: ["assigned", "declined"],
    form_schema: {
      type: "object",
      required: ["assignee"],
      properties: {
        assignee: { type: "string", description: "Email of the designated incident commander" },
        priority: { type: "string", description: "Override priority level", enum: ["P1", "P2", "P3", "P4"] },
      },
    },
  },
});
console.log(`intent created: ${intentId}`);
console.log("Check your email for the task link.");
