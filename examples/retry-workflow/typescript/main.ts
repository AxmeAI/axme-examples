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

function asInt(name: string, fallback: number): number {
  const raw = (process.env[name] ?? "").trim();
  if (!raw) {
    return fallback;
  }
  return Number.parseInt(raw, 10);
}

function runExternalStep(attempt: number, simulatedFailures: number): Record<string, unknown> {
  if (attempt <= simulatedFailures) {
    throw new Error(`transient dependency failure on attempt ${attempt}`);
  }
  return {
    status: "ok",
    attempt,
    job_reference: `job-${crypto.randomUUID().slice(0, 8)}`,
  };
}

async function main(): Promise<void> {
  const baseUrl = (process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai").trim();
  const apiKey = requireEnv("AXME_API_KEY");
  const actorToken = (process.env.AXME_ACTOR_TOKEN ?? "").trim() || undefined;
  const fromAgent = (process.env.AXME_FROM_AGENT ?? "agent://examples/retry-orchestrator").trim();
  const toAgent = (process.env.AXME_TO_AGENT ?? "agent://examples/retry-worker").trim();
  const ownerAgent = (process.env.AXME_OWNER_AGENT ?? fromAgent).trim();
  const maxAttempts = asInt("AXME_MAX_ATTEMPTS", 5);
  const simulatedFailures = asInt("AXME_SIMULATED_FAILURES", 2);
  const baseBackoffSeconds = asInt("AXME_BASE_BACKOFF_SECONDS", 1);

  const client = new AxmeClient({ baseUrl, apiKey, actorToken });
  const correlationId = crypto.randomUUID();
  const idempotencyKey = `retry-${correlationId}`;
  const payload = {
    intent_type: "intent.retry.demo.v1",
    correlation_id: correlationId,
    from_agent: fromAgent,
    to_agent: toAgent,
    payload: {
      task: "sync_remote_inventory",
      target_system: "warehouse-api",
    },
  };

  const createdFirst = await client.createIntent(payload, { correlationId, idempotencyKey });
  const createdSecond = await client.createIntent(payload, { correlationId, idempotencyKey });
  const intentId = String(createdFirst.intent_id);
  console.log(`[create] intent_id=${intentId} status=${String(createdFirst.status ?? "unknown")}`);
  console.log(`[idempotency] replay_intent_id=${String(createdSecond.intent_id ?? "unknown")}`);

  let attempts = 0;
  const delays: number[] = [];
  let externalResult: Record<string, unknown> | undefined;

  while (attempts < maxAttempts) {
    attempts += 1;
    try {
      externalResult = runExternalStep(attempts, simulatedFailures);
      console.log(`[attempt ${attempts}] external step succeeded`);
      break;
    } catch (error) {
      const delaySeconds = baseBackoffSeconds * 2 ** (attempts - 1);
      delays.push(delaySeconds);
      console.log(`[attempt ${attempts}] ${(error as Error).message}; backing off for ${delaySeconds}s`);
      const controls = await client.updateIntentControls(
        intentId,
        {
          controls_patch: {
            last_retry_attempt: attempts,
            next_retry_delay_seconds: delaySeconds,
          },
          reason: `retry attempt ${attempts} failed`,
        },
        { ownerAgent },
      );
      console.log(
        `[controls] applied=${String(controls.applied ?? "unknown")} policy_generation=${String(controls.policy_generation ?? "unknown")}`,
      );
      await new Promise((resolve) => setTimeout(resolve, Math.max(0, delaySeconds) * 1000));
    }
  }

  if (externalResult) {
    const resolved = await client.resolveIntent(intentId, {
      status: "COMPLETED",
      result: {
        attempts,
        retry_backoff_seconds: delays,
        external_result: externalResult,
      },
    });
    const event = (resolved.event ?? {}) as Record<string, unknown>;
    console.log(`[resolve] status=${String(event.status ?? "unknown")}`);
  } else {
    const failed = await client.resolveIntent(intentId, {
      status: "FAILED",
      error: {
        code: "max_attempts_exceeded",
        attempts,
        retry_backoff_seconds: delays,
      },
    });
    const event = (failed.event ?? {}) as Record<string, unknown>;
    console.log(`[resolve] status=${String(event.status ?? "unknown")}`);
  }

  const finalIntent = ((await client.getIntent(intentId)).intent ?? {}) as Record<string, unknown>;
  console.log(
    `[final] intent_id=${intentId} status=${String(finalIntent.status ?? "unknown")} lifecycle_status=${String(finalIntent.lifecycle_status ?? "unknown")}`,
  );
}

main().catch((error) => {
  console.error("[error]", error);
  process.exit(1);
});
