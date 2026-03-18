/**
 * Pre-Approval Validator — durability/reminder-escalation example (TypeScript).
 *
 * Validates a change request before routing to human approval with SLA reminders.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=pre-approval-validator
 *   npx tsx examples/durability/reminder-escalation/agent.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "pre-approval-validator";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

const ALLOWED_CHANGE_TYPES = new Set(["config_update", "dependency_update", "rollback", "hotfix"]);
const VALID_RISK_LEVELS = new Set(["low", "medium", "high", "critical"]);

function validateChange(payload: Record<string, unknown>): { valid: boolean; reason: string } {
  const changeId = String(payload.change_id ?? "?");
  const changeType = String(payload.change_type ?? "");
  const riskLevel = String(payload.risk_level ?? "");
  const service = String(payload.service ?? "");

  if (!service) return { valid: false, reason: `${changeId}: service is required` };
  if (!ALLOWED_CHANGE_TYPES.has(changeType)) return { valid: false, reason: `${changeId}: change_type '${changeType}' not in ${[...ALLOWED_CHANGE_TYPES].sort()}` };
  if (!VALID_RISK_LEVELS.has(riskLevel)) return { valid: false, reason: `${changeId}: risk_level '${riskLevel}' not in ${[...VALID_RISK_LEVELS].sort()}` };

  return { valid: true, reason: `${changeId}: pre-validation passed for '${service}' (${changeType}, ${riskLevel} risk)` };
}

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
console.log(`pre-approval-validator starting  address=${AXME_AGENT_ADDRESS}  binding=stream`);

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
    const { valid, reason } = validateChange(effectivePayload);

    console.log(`pre-validation for ${intentId}: valid=${valid}  reason=${reason}`);

    try {
      if (valid) {
        await client.resumeIntent(intentId, { action: "complete", valid: true, reason }, { ownerAgent: AXME_AGENT_ADDRESS });
      } else {
        await client.resumeIntent(intentId, { action: "fail", valid: false, reason }, { ownerAgent: AXME_AGENT_ADDRESS });
      }
      console.log(`resumed intent ${intentId} (valid=${valid})`);
    } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
