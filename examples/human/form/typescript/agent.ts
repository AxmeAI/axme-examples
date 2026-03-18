/**
 * Access Policy Checker — human/form example (TypeScript).
 *
 * Checks access request policy before routing to the Security Officer
 * for structured form-based approval.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=access-policy-checker
 *   npx tsx examples/human/form/agent.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "access-policy-checker";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

// --- Business logic ---
const ALLOWED_ACCESS_TYPES = new Set(["READ", "READ_WRITE"]);
const HUMAN_SIGNOFF_RESOURCES = new Set(["prod-analytics-db", "prod-customer-db", "prod-payments-db"]);
const PII_BLOCKED_ACCESS = new Set(["READ_WRITE", "WRITE", "ADMIN"]);

function checkPolicy(payload: Record<string, unknown>): { passed: boolean; checks: string[]; violations: string[] } {
  const resource = String(payload.resource ?? "");
  const accessType = String(payload.access_type ?? "").toUpperCase();
  const requestor = String(payload.requestor ?? "");
  const piiFields = Boolean(payload.pii_fields);
  const checks: string[] = [];
  const violations: string[] = [];

  if (ALLOWED_ACCESS_TYPES.has(accessType)) checks.push(`access type '${accessType}' is in allowed set`);
  else violations.push(`access type '${accessType}' is not allowed; permitted: ${[...ALLOWED_ACCESS_TYPES].sort()}`);

  if (requestor) checks.push(`requestor identity '${requestor}' is present`);
  else violations.push("requestor identity is missing");

  if (piiFields && PII_BLOCKED_ACCESS.has(accessType)) {
    violations.push(`resource contains PII fields; '${accessType}' access is not permitted on PII data`);
  } else if (piiFields) {
    checks.push(`PII data present but '${accessType}' is read-only — acceptable`);
  } else {
    checks.push("resource has no PII fields — no PII restriction applies");
  }

  return { passed: violations.length === 0, checks, violations };
}

// --- Agent loop ---
const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
console.log(`access-policy-checker starting  address=${AXME_AGENT_ADDRESS}  binding=stream`);

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
    const { passed, checks, violations } = checkPolicy(effectivePayload);

    console.log(`policy check for ${intentId}: passed=${passed}  checks=${checks.length}  violations=${violations.length}`);

    try {
      if (passed) {
        await client.resumeIntent(intentId, {
          action: "complete", policy_passed: true, passed_checks: checks, violations: [],
          requires_human_signoff: HUMAN_SIGNOFF_RESOURCES.has(String(effectivePayload.resource ?? "")),
        }, { ownerAgent: AXME_AGENT_ADDRESS });
      } else {
        await client.resumeIntent(intentId, {
          action: "fail", policy_passed: false, passed_checks: checks, violations,
        }, { ownerAgent: AXME_AGENT_ADDRESS });
      }
      console.log(`resumed intent ${intentId} (policy_passed=${passed})`);
    } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
