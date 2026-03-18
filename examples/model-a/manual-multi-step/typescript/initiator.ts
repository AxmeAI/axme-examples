/**
 * Model A — Manual Multi-Step: chain two agents sequentially (TypeScript).
 *
 * Run:
 *   AXME_API_KEY=<workspace-key> \
 *   AXME_AGENT_1=agent://org/ws/compliance-checker-agent \
 *   AXME_AGENT_2=agent://org/ws/risk-assessment-agent \
 *     npx tsx examples/model-a/manual-multi-step/initiator.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AGENT_1 = process.env.AXME_AGENT_1 ?? "";
const AGENT_2 = process.env.AXME_AGENT_2 ?? "";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }
if (!AGENT_1 || !AGENT_2) { console.error("AXME_AGENT_1 and AXME_AGENT_2 are required"); process.exit(1); }

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });

async function waitForDone(intentId: string, timeout = 60_000): Promise<string> {
  for await (const event of client.observe(intentId, { timeoutMs: timeout })) {
    const status = String(event.status ?? "");
    if (["COMPLETED", "IN_PROGRESS", "FAILED", "CANCELED", "TIMED_OUT"].includes(status)) return status;
  }
  return "UNKNOWN";
}

const changePayload = {
  change_id: "CHG-MULTI-STEP-001", service: "api-gateway", version: "5.0.0",
  environment: "staging", change_type: "config_update", risk_level: "medium", risk_threshold: 30,
};

// Step 1: Compliance Check
console.log(`STEP 1: compliance check → ${AGENT_1}`);
const step1Id = await client.sendIntent({
  intent_type: "intent.compliance.check.v1",
  from_agent: "initiator://manual-multi-step", to_agent: AGENT_1, payload: changePayload,
});
console.log(`step 1 intent: ${step1Id} — waiting...`);
const step1Status = await waitForDone(step1Id);
console.log(`step 1 → ${step1Status}`);

if (!["COMPLETED", "IN_PROGRESS"].includes(step1Status)) {
  console.error(`step 1 failed (${step1Status}) — aborting pipeline`);
  process.exit(1);
}

// Step 2: Risk Assessment
console.log(`STEP 2: risk assessment → ${AGENT_2}`);
const step2Id = await client.sendIntent({
  intent_type: "intent.risk.assessment.v1",
  from_agent: "initiator://manual-multi-step", to_agent: AGENT_2,
  payload: { ...changePayload, compliance_result: "passed", compliance_intent_id: step1Id },
});
console.log(`step 2 intent: ${step2Id} — waiting...`);
const step2Status = await waitForDone(step2Id);
console.log(`step 2 → ${step2Status}`);

// Summary
console.log("");
console.log("=== Manual Multi-Step Pipeline ===");
console.log(`  Step 1 (compliance): ${step1Status}  id=${step1Id}`);
console.log(`  Step 2 (risk):       ${step2Status}  id=${step2Id}`);
if (["COMPLETED", "IN_PROGRESS"].includes(step1Status) && ["COMPLETED", "IN_PROGRESS"].includes(step2Status)) {
  console.log("  Result: ALL STEPS PASSED");
} else {
  console.log("  Result: PIPELINE FAILED");
}
