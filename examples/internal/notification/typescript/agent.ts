/**
 * Risk Assessment Agent — internal/notification example (TypeScript).
 *
 * Assesses deployment risk. If risk exceeds threshold, signals HIGH risk
 * and the workflow triggers the built-in notification step.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=risk-assessment-agent
 *   npx tsx examples/internal/notification/agent.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "risk-assessment-agent";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

// --- Risk scoring ---
const MAJOR_BUMP_WEIGHT = 40;
const MINOR_BUMP_WEIGHT = 15;
const HIGH_CHANGE_WEIGHT = 30;
const PROD_ENV_WEIGHT = 25;
const STAGING_ENV_WEIGHT = 10;

function parseSemver(v: string): [number, number, number] {
  const parts = v.trim().split(".");
  return [parseInt(parts[0]) || 0, parseInt(parts[1]) || 0, parseInt(parts[2]) || 0];
}

function assessRisk(payload: Record<string, unknown>): { score: number; level: string; factors: string[] } {
  const version = String(payload.version ?? "0.0.0");
  const environment = String(payload.environment ?? "");
  const changeCount = Number(payload.change_count ?? 0);
  const threshold = Number(payload.risk_threshold ?? 30);
  const [major, minor] = parseSemver(version);

  let score = 0;
  const factors: string[] = [];

  if (major >= 4) { score += MAJOR_BUMP_WEIGHT; factors.push(`major version bump (v${major}.x) +${MAJOR_BUMP_WEIGHT}`); }
  else if (minor >= 5) { score += MINOR_BUMP_WEIGHT; factors.push(`significant minor version bump +${MINOR_BUMP_WEIGHT}`); }

  if (changeCount > 30) { score += HIGH_CHANGE_WEIGHT; factors.push(`high change count (${changeCount} changes) +${HIGH_CHANGE_WEIGHT}`); }

  if (environment === "production") { score += PROD_ENV_WEIGHT; factors.push(`production environment +${PROD_ENV_WEIGHT}`); }
  else if (["staging", "canary"].includes(environment)) { score += STAGING_ENV_WEIGHT; factors.push(`staging environment +${STAGING_ENV_WEIGHT}`); }

  const level = score >= threshold ? "HIGH" : score >= threshold / 2 ? "MEDIUM" : "LOW";
  return { score, level, factors };
}

// --- Agent loop ---
const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
console.log(`risk-assessment-agent starting  address=${AXME_AGENT_ADDRESS}  binding=stream`);

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
    const { score, level, factors } = assessRisk(effectivePayload);

    console.log(`risk assessment for ${intentId}: score=${score}  level=${level}  factors=${factors.length}`);

    try {
      await client.resumeIntent(intentId, {
        action: "complete", risk_score: score, risk_level: level, factors,
      }, { ownerAgent: AXME_AGENT_ADDRESS });
      console.log(`resumed intent ${intentId} (risk=${level} score=${score})`);
    } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
