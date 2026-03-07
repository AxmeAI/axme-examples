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

function printEvents(events: Array<Record<string, unknown>>): void {
  for (const event of events) {
    const seq = typeof event.seq === "number" ? event.seq : 0;
    const eventType = String(event.event_type ?? "unknown");
    const status = String(event.status ?? "unknown");
    const waitingReason = event.waiting_reason ? ` waiting_reason=${String(event.waiting_reason)}` : "";
    console.log(`[event] seq=${seq} type=${eventType} status=${status}${waitingReason}`);
  }
}

async function main(): Promise<void> {
  const baseUrl = (process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai").trim();
  const apiKey = requireEnv("AXME_API_KEY");
  const actorToken = (process.env.AXME_ACTOR_TOKEN ?? "").trim() || undefined;
  const fromAgent = (process.env.AXME_FROM_AGENT ?? "agent://examples/requester").trim();
  const toAgent = (process.env.AXME_TO_AGENT ?? "agent://examples/approver").trim();
  const ownerAgent = (process.env.AXME_APPROVAL_OWNER_AGENT ?? fromAgent).trim();

  const client = new AxmeClient({
    baseUrl,
    apiKey,
    actorToken,
  });

  const correlationId = crypto.randomUUID();
  const idempotencyKey = `approval-${correlationId}`;
  const payload = {
    intent_type: "intent.approval.demo.v1",
    correlation_id: correlationId,
    from_agent: fromAgent,
    to_agent: toAgent,
    payload: {
      request_id: `req-${correlationId.slice(0, 8)}`,
      summary: "Auto-approved rollout request.",
      requested_by: fromAgent,
      approval_mode: "automatic",
    },
  };

  const created = await client.createIntent(payload, {
    correlationId,
    idempotencyKey,
  });
  const intentId = String(created.intent_id);
  console.log(`[create] intent_id=${intentId} status=${String(created.status ?? "unknown")}`);
  console.log("[approval] auto-approval path enabled; no manual waiting.");

  const resumed = await client.resumeIntent(
    intentId,
    {
      approve_current_step: true,
      reason: "auto-approved by policy",
    },
    { ownerAgent },
  );
  console.log(
    `[resume] applied=${String(resumed.applied ?? "unknown")} policy_generation=${String(resumed.policy_generation ?? "unknown")}`,
  );

  const resolved = await client.resolveIntent(intentId, {
    status: "COMPLETED",
    result: {
      approval_result: "auto-approved",
      approval_mode: "automatic",
    },
  });
  const terminalEvent = (resolved.event ?? {}) as Record<string, unknown>;
  console.log(`[resolve] terminal_type=${String(terminalEvent.event_type ?? "unknown")} status=${String(terminalEvent.status ?? "unknown")}`);

  const listed = await client.listIntentEvents(intentId);
  const events = Array.isArray(listed.events)
    ? listed.events.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    : [];
  printEvents(events);

  const finalIntent = ((await client.getIntent(intentId)).intent ?? {}) as Record<string, unknown>;
  console.log(
    `[final] intent_id=${intentId} status=${String(finalIntent.status ?? "unknown")} lifecycle_status=${String(finalIntent.lifecycle_status ?? "unknown")}`,
  );
}

main().catch((error) => {
  console.error("[error]", error);
  process.exit(1);
});
