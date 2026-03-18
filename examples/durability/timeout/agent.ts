/**
 * Slow Batch Processor — durability/timeout example (TypeScript).
 *
 * Demonstrates step deadline enforcement. The scenario sets step_deadline_seconds=10.
 * Run WITHOUT the agent to observe the timeout behavior.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=slow-batch-processor
 *   npx tsx examples/durability/timeout/agent.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "slow-batch-processor";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

const MAX_BATCH_RECORDS = 10_000;

function processBatch(payload: Record<string, unknown>): { ok: boolean; result: Record<string, unknown> } {
  const batchId = String(payload.batch_id ?? "?");
  const recordCount = Number(payload.record_count ?? 0);

  if (recordCount > MAX_BATCH_RECORDS) {
    return { ok: false, result: { batch_id: batchId, error: `batch too large: ${recordCount} records exceeds limit of ${MAX_BATCH_RECORDS}`, record_count: recordCount } };
  }
  return { ok: true, result: { batch_id: batchId, record_count: recordCount, processed: true } };
}

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
console.log(`slow-batch-processor starting  address=${AXME_AGENT_ADDRESS}  binding=stream`);

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
    const { ok, result } = processBatch(effectivePayload);

    console.log(`batch result for ${intentId}: ok=${ok}`);

    try {
      await client.resumeIntent(intentId, { action: ok ? "complete" : "fail", ...result }, { ownerAgent: AXME_AGENT_ADDRESS });
      console.log(`resumed intent ${intentId}`);
    } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
