/**
 * Batch Processor Agent — poll delivery binding (TypeScript).
 *
 * Delivery: poll  (periodic reconnect to GET /v1/agents/{address}/intents/stream)
 * The agent wakes up every POLL_INTERVAL seconds, checks for new intents, then disconnects.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=batch-processor-agent
 *   export POLL_INTERVAL=10
 *   npx tsx examples/delivery/poll/agent.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "batch-processor-agent";
const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL ?? "10", 10) * 1000;

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

// --- Business logic ---
const SUPPORTED_RECORD_TYPES = new Set(["transactions", "invoices", "orders", "events"]);
const RECORD_COUNTS: Record<string, number> = {
  transactions: 14_203, invoices: 1_847, orders: 3_291, events: 82_014,
};

function processBatch(payload: Record<string, unknown>): Record<string, unknown> {
  const batchId = String(payload.batch_id ?? "?");
  const recordType = String(payload.record_type ?? "");
  const dateRange = String(payload.date_range ?? "");

  if (!batchId || batchId === "?") return { action: "fail", reason: "batch_id is required" };
  if (!SUPPORTED_RECORD_TYPES.has(recordType)) {
    return { action: "fail", reason: `unsupported record_type='${recordType}', supported: ${[...SUPPORTED_RECORD_TYPES].sort()}` };
  }
  if (!dateRange) return { action: "fail", reason: "date_range is required" };

  return {
    action: "complete", batch_id: batchId, record_type: recordType,
    date_range: dateRange, record_count: RECORD_COUNTS[recordType] ?? 0, status: "processed",
  };
}

// --- Poll loop ---
const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
const seen = new Set<string>();
let cursor = 0;

console.log(`batch-processor-agent starting  address=${AXME_AGENT_ADDRESS}  binding=poll  interval=${POLL_INTERVAL / 1000}s`);

async function pollOnce(): Promise<void> {
  let newCount = 0;
  try {
    for await (const delivery of client.listen(AXME_AGENT_ADDRESS, { since: cursor, waitSeconds: 2, timeoutMs: 5000 })) {
      const intentId = String(delivery.intent_id ?? "");
      const seq = typeof delivery.seq === "number" ? delivery.seq : 0;
      if (seq) cursor = Math.max(cursor, seq);
      if (!intentId || seen.has(intentId)) continue;
      seen.add(intentId);

      console.log(`processing intent ${intentId}`);
      let intent: Record<string, unknown>;
      try {
        intent = await client.getIntent(intentId);
      } catch (e) { console.error(`get_intent(${intentId}) failed:`, e); continue; }

      const payload = (intent.payload ?? {}) as Record<string, unknown>;
      const result = processBatch(payload);
      const action = result.action;
      delete result.action;

      try {
        await client.resumeIntent(intentId, { action, ...result }, { ownerAgent: AXME_AGENT_ADDRESS });
        console.log(`resumed ${intentId}  action=${action}`);
      } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
      newCount++;
    }
  } catch { /* timeout — normal */ }
  if (newCount) console.log(`poll cycle done  processed=${newCount}  cursor=${cursor}`);
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

try {
  while (true) {
    await pollOnce();
    await sleep(POLL_INTERVAL);
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
