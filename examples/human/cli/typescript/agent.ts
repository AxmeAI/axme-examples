/**
 * Deploy Readiness Checker — human/cli example (TypeScript).
 *
 * Validates deployment readiness before routing to a human operator.
 * After the agent step, the workflow pauses for human approval via CLI.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=deploy-readiness-checker
 *   npx tsx examples/human/cli/agent.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "deploy-readiness-checker";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

// --- Business logic ---
const SEMVER_RE = /^\d+\.\d+\.\d+$/;
const ALLOWED_ENVIRONMENTS = new Set(["staging", "canary", "preview"]);

function checkReadiness(payload: Record<string, unknown>): { ready: boolean; passed: string[]; failures: string[] } {
  const version = String(payload.version ?? "");
  const environment = String(payload.environment ?? "");
  const rollback = String(payload.rollback_tag ?? "");
  const service = String(payload.service ?? "");
  const passed: string[] = [];
  const failures: string[] = [];

  if (SEMVER_RE.test(version)) passed.push(`version '${version}' is valid semver`);
  else failures.push(`version '${version}' is not valid semver (expected MAJOR.MINOR.PATCH)`);

  if (ALLOWED_ENVIRONMENTS.has(environment)) passed.push(`environment '${environment}' is in allowed list`);
  else failures.push(`environment '${environment}' not in allowed set: ${[...ALLOWED_ENVIRONMENTS].sort()}`);

  if (rollback) passed.push(`rollback_tag '${rollback}' is set`);
  else failures.push("rollback_tag is missing — deployment must have a rollback path");

  if (service) passed.push(`service '${service}' is identified`);
  else failures.push("service name is empty");

  return { ready: failures.length === 0, passed, failures };
}

// --- Agent loop ---
const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
console.log(`deploy-readiness-checker starting  address=${AXME_AGENT_ADDRESS}  binding=stream`);

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
    const { ready, passed, failures } = checkReadiness(effectivePayload);

    console.log(`readiness for ${intentId}: ready=${ready}  passed=${passed.length}  failed=${failures.length}`);

    try {
      if (ready) {
        await client.resumeIntent(intentId, { action: "complete", ready: true, passed_checks: passed, failures: [] }, { ownerAgent: AXME_AGENT_ADDRESS });
      } else {
        await client.resumeIntent(intentId, { action: "fail", ready: false, passed_checks: passed, failures }, { ownerAgent: AXME_AGENT_ADDRESS });
      }
      console.log(`resumed intent ${intentId} (ready=${ready})`);
    } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
