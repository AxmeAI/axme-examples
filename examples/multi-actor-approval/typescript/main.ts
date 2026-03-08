/**
 * Multi-actor approval: Requester and Approver use distinct actorTokens.
 *
 * This example demonstrates the core AXP pattern for human-in-the-loop approvals
 * where two different actors (requester and approver) each present their own
 * actorToken to the same AXME Cloud workspace.
 *
 * Flow:
 *   1. Requester creates an approval intent (enters WAITING state after creation).
 *   2. Runtime puts the intent in WAITING — execution pauses until unblocked.
 *   3. Approver (different actor) resumes the intent with their actorToken.
 *   4. Requester polls for the terminal state and reads the approval result.
 */

import { config as loadEnv } from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { AxmeClient } from "@axme/axme/dist/src/index.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

loadEnv({ path: path.resolve(__dirname, "..", ".env") });

function requireEnv(name: string): string {
  const value = (process.env[name] ?? "").trim();
  if (!value) {
    throw new Error(`missing required env var: ${name}`);
  }
  return value;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main(): Promise<void> {
  const baseUrl = (process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai").trim();
  const apiKey = requireEnv("AXME_API_KEY");
  const requesterToken = requireEnv("AXME_REQUESTER_TOKEN");
  const approverToken = requireEnv("AXME_APPROVER_TOKEN");

  const requesterAgent = (process.env.AXME_REQUESTER_AGENT ?? "agent://examples/requester").trim();
  const approverAgent = (process.env.AXME_APPROVER_AGENT ?? "agent://examples/approver").trim();

  // --- Step 1: Requester creates the approval intent ---
  console.log("\n=== Step 1: Requester creates approval intent ===");

  const requester = new AxmeClient({ baseUrl, apiKey, actorToken: requesterToken });
  const correlationId = crypto.randomUUID();
  const idempotencyKey = `multi-actor-approval-${correlationId}`;

  const created = await requester.createIntent(
    {
      intent_type: "intent.approval.multi_actor.v1",
      correlation_id: correlationId,
      from_agent: requesterAgent,
      to_agent: approverAgent,
      payload: {
        request_id: `req-${correlationId.slice(0, 8)}`,
        summary: "Deploy backend service v2.4.1 to production",
        requested_by: requesterAgent,
        approval_mode: "manual",
        risk_level: "high",
      },
    },
    { correlationId, idempotencyKey },
  );

  const intentId = String(created.intent_id);
  console.log(`[requester] intent_id=${intentId} status=${String(created.status ?? "unknown")}`);
  console.log(`[requester] correlation_id=${correlationId}`);
  console.log("\n[requester] Intent is in WAITING state. Handing off to approver.");

  // --- Step 2: Approver reviews and approves ---
  console.log("\n=== Step 2: Approver reviews and approves ===");

  // Small pause to simulate the approver being a different system/user.
  await sleep(500);

  const approver = new AxmeClient({ baseUrl, apiKey, actorToken: approverToken });

  // Approver can inspect the intent before deciding.
  const intentDetail = await approver.getIntent(intentId);
  const intentData = (intentDetail.intent ?? {}) as Record<string, unknown>;
  console.log(`[approver] reviewing intent_id=${intentId}`);
  console.log(`[approver] current status=${String(intentData.status ?? "unknown")}`);

  const payloadData = (intentData.payload ?? {}) as Record<string, unknown>;
  const summary = String(payloadData.summary ?? "(no summary)");
  const riskLevel = String(payloadData.risk_level ?? "unknown");
  console.log(`[approver] summary: ${summary}`);
  console.log(`[approver] risk_level: ${riskLevel}`);

  // Approver makes their decision via resume.
  const resumed = await approver.resumeIntent(
    intentId,
    {
      approve_current_step: true,
      reason: "Reviewed deployment plan — approved for production.",
      approved_by: approverAgent,
    },
    { ownerAgent: approverAgent },
  );
  console.log(
    `[approver] resume applied=${String(resumed.applied ?? "unknown")} ` +
      `policy_generation=${String(resumed.policy_generation ?? "unknown")}`,
  );

  // Approver resolves the intent to COMPLETED with the approval result.
  const resolved = await approver.resolveIntent(intentId, {
    status: "COMPLETED",
    result: {
      approval_result: "approved",
      approved_by: approverAgent,
      summary,
      notes: "Production deployment approved by on-call lead.",
    },
  });
  const terminalEvent = (resolved.event ?? {}) as Record<string, unknown>;
  console.log(
    `[approver] resolve status=${String(terminalEvent.status ?? "unknown")} ` +
      `type=${String(terminalEvent.event_type ?? "unknown")}`,
  );

  // --- Step 3: Requester reads the final result ---
  console.log("\n=== Step 3: Requester reads approval result ===");

  const finalIntent = await requester.getIntent(intentId);
  const finalData = (finalIntent.intent ?? {}) as Record<string, unknown>;
  const result = (finalData.result ?? {}) as Record<string, unknown>;
  console.log(`[requester] intent_id=${intentId}`);
  console.log(`[requester] final status=${String(finalData.status ?? "unknown")}`);
  console.log(`[requester] approval_result=${String(result.approval_result ?? "unknown")}`);
  console.log(`[requester] approved_by=${String(result.approved_by ?? "unknown")}`);
  console.log(`[requester] notes=${String(result.notes ?? "")}`);

  // Read lifecycle events — both actors appear in the event chain.
  const listed = await requester.listIntentEvents(intentId);
  const events = (listed.events ?? []) as Array<Record<string, unknown>>;
  if (events.length > 0) {
    console.log("\n[lifecycle] events:");
    for (const event of events) {
      const seq = event.seq ?? 0;
      const evStatus = event.status ?? "unknown";
      const actor = event.actor_id ?? event.actor ?? "system";
      const waitingReason = event.waiting_reason;
      const suffix = waitingReason ? ` waiting_reason=${String(waitingReason)}` : "";
      console.log(`  seq=${String(seq)}  status=${String(evStatus)}  actor=${String(actor)}${suffix}`);
    }
  }

  console.log("\n=== Done ===");
  console.log(
    "The full lifecycle is recorded durably. Each actor's action is " +
      "traceable via the event chain — no shared mutable state outside " +
      "the intent was needed.",
  );
}

main().catch((err: unknown) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
