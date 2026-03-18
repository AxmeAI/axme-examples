/**
 * Change Window Validator — internal/delay example (TypeScript).
 *
 * Validates that a change falls within an approved maintenance window.
 * The step has a 120-second deadline (step_deadline_seconds: 120).
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=change-window-validator
 *   npx tsx examples/internal/delay/agent.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "change-window-validator";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

// --- Business logic ---
const APPROVED_WINDOWS = new Set(["MW-2026-Q1-01", "MW-2026-Q1-02", "MW-2026-Q1-03", "MW-2026-Q1-04", "MW-2026-Q1-05", "MW-2026-Q1-06"]);
const ALLOWED_CHANGE_TYPES = new Set(["config_update", "dependency_update", "rollback", "hotfix"]);

function validateChangeWindow(payload: Record<string, unknown>): { allowed: boolean; reason: string; meta: Record<string, unknown> } {
  const changeId = String(payload.change_id ?? "?");
  const environment = String(payload.environment ?? "");
  const changeType = String(payload.change_type ?? "");
  const windowId = String(payload.window_id ?? "");
  const scheduledAt = String(payload.scheduled_at ?? "");

  if (!ALLOWED_CHANGE_TYPES.has(changeType)) {
    return { allowed: false, reason: `${changeId}: change_type '${changeType}' is not in allowed set ${[...ALLOWED_CHANGE_TYPES].sort()}`, meta: {} };
  }
  if (environment === "production") {
    if (!windowId) return { allowed: false, reason: `${changeId}: production changes require an approved window_id`, meta: {} };
    if (!APPROVED_WINDOWS.has(windowId)) return { allowed: false, reason: `${changeId}: window_id '${windowId}' is not in the approved window list`, meta: {} };
  }
  if (scheduledAt) {
    const d = new Date(scheduledAt);
    if (isNaN(d.getTime())) return { allowed: false, reason: `${changeId}: scheduled_at '${scheduledAt}' is not a valid ISO timestamp`, meta: {} };
  }

  const meta: Record<string, unknown> = {};
  if (windowId && APPROVED_WINDOWS.has(windowId)) Object.assign(meta, { window_id: windowId, window_approved: true });

  return { allowed: true, reason: `${changeId}: change window validated for '${environment}' environment`, meta };
}

// --- Agent loop ---
const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
console.log(`change-window-validator starting  address=${AXME_AGENT_ADDRESS}  binding=stream`);

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
    const { allowed, reason, meta } = validateChangeWindow(effectivePayload);

    console.log(`window validation for ${intentId}: allowed=${allowed}  reason=${reason}`);

    try {
      if (allowed) {
        await client.resumeIntent(intentId, { action: "complete", allowed: true, reason, ...meta }, { ownerAgent: AXME_AGENT_ADDRESS });
      } else {
        await client.resumeIntent(intentId, { action: "fail", allowed: false, reason }, { ownerAgent: AXME_AGENT_ADDRESS });
      }
      console.log(`resumed intent ${intentId} (allowed=${allowed})`);
    } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
