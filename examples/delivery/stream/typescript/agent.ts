/**
 * Compliance Checker Agent — stream delivery binding (TypeScript).
 *
 * Delivery: stream  (GET /v1/agents/{address}/intents/stream)
 * The agent holds a persistent SSE connection to AXME.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=compliance-checker-agent
 *   npx tsx examples/delivery/stream/agent.ts
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "compliance-checker-agent";

if (!AXME_API_KEY) {
  console.error("AXME_API_KEY is required");
  process.exit(1);
}

// --- Delivery cursor ---
const SEQ_FILE = join(homedir(), ".axme", "compliance_checker_agent_seq.txt");

function loadSince(): number {
  try {
    return parseInt(readFileSync(SEQ_FILE, "utf-8").trim(), 10) || 0;
  } catch {
    return 0;
  }
}

function saveSince(seq: number): void {
  try {
    mkdirSync(join(homedir(), ".axme"), { recursive: true });
    writeFileSync(SEQ_FILE, String(seq), "utf-8");
  } catch (e) {
    console.warn("could not persist delivery cursor:", e);
  }
}

// --- Business logic ---
const BLOCKED_ENVIRONMENTS = new Set(["production"]);
const RISK_REQUIRES_BACKUP = new Set(["high", "critical"]);

function checkCompliance(payload: Record<string, unknown>): { passed: boolean; reason: string } {
  const changeId = String(payload.change_id ?? "?");
  const environment = String(payload.environment ?? "");
  const riskLevel = String(payload.risk_level ?? "low");
  const backupOk = Boolean(payload.backup_confirmed);

  if (BLOCKED_ENVIRONMENTS.has(environment)) {
    return { passed: false, reason: `${changeId}: production changes require manual approval, not automated` };
  }
  if (RISK_REQUIRES_BACKUP.has(riskLevel) && !backupOk) {
    return { passed: false, reason: `${changeId}: risk_level=${riskLevel} requires backup_confirmed=true` };
  }
  return { passed: true, reason: `${changeId}: compliance checks passed (environment=${environment}, risk=${riskLevel})` };
}

// --- Agent loop ---
const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
const since = loadSince();

console.log(`compliance-checker-agent starting  address=${AXME_AGENT_ADDRESS}  binding=stream  since=${since}`);

try {
  for await (const delivery of client.listen(AXME_AGENT_ADDRESS, { since })) {
    const intentId = String(delivery.intent_id ?? "");
    const seq = typeof delivery.seq === "number" ? delivery.seq : 0;
    if (!intentId) continue;

    console.log(`received intent ${intentId}`);

    let intent: Record<string, unknown>;
    try {
      const resp = await client.getIntent(intentId);
      intent = (resp.intent ?? resp) as Record<string, unknown>;
    } catch (e) {
      console.error(`get_intent(${intentId}) failed:`, e);
      continue;
    }

    const status = String(intent.lifecycle_status ?? intent.status ?? "").toUpperCase();
    if (!["CREATED", "DELIVERED", "ACKNOWLEDGED", "IN_PROGRESS", "WAITING"].includes(status)) continue;

    const rawPayload = (intent.payload ?? {}) as Record<string, unknown>;
    const effectivePayload = (rawPayload.parent_payload ?? rawPayload) as Record<string, unknown>;
    const { passed, reason } = checkCompliance(effectivePayload);

    console.log(`compliance result for ${intentId}: passed=${passed}  reason=${reason}`);

    try {
      if (passed) {
        await client.resumeIntent(intentId, {
          action: "complete", passed: true, reason,
          checked_fields: ["environment", "risk_level", "backup_confirmed"],
        }, { ownerAgent: AXME_AGENT_ADDRESS });
      } else {
        await client.resumeIntent(intentId, {
          action: "fail", passed: false, reason,
        }, { ownerAgent: AXME_AGENT_ADDRESS });
      }
      console.log(`resumed intent ${intentId}  (passed=${passed})`);
      if (seq > 0) saveSince(seq);
    } catch (e) {
      console.error(`resume_intent(${intentId}) failed:`, e);
    }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
