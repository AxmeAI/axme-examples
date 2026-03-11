import { config as loadEnv } from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { AxmeClient } from "@axme/axme/dist/src/index.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

loadEnv({ path: path.resolve(__dirname, "..", ".env") });

function readCliKeyFromSecrets(context = "default"): string {
  try {
    const os = require("os");
    const fs = require("fs");
    const path = require("path");
    const secretsPath = path.join(os.homedir(), ".config", "axme", "secrets.json");
    const data = JSON.parse(fs.readFileSync(secretsPath, "utf8"));
    return ((data[context] ?? data["default"] ?? {}).api_key ?? "").trim();
  } catch {
    return "";
  }
}

function requireEnv(name: string): string {
  let value = (process.env[name] ?? "").trim();
  if (!value && name === "AXME_API_KEY") {
    value = readCliKeyFromSecrets();
  }
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
  // from_agent is derived by the server from the API key (no longer passed explicitly)
  const toAgent = (process.env.AXME_TO_AGENT ?? "").trim() || undefined;
  const ownerAgent = (process.env.AXME_OWNER_AGENT ?? "").trim() || undefined;
  const maxAttempts = asInt("AXME_MAX_ATTEMPTS", 5);
  const simulatedFailures = asInt("AXME_SIMULATED_FAILURES", 2);
  const baseBackoffSeconds = asInt("AXME_BASE_BACKOFF_SECONDS", 1);

  const client = new AxmeClient({ baseUrl, apiKey, actorToken });
  const correlationId = crypto.randomUUID();
  const idempotencyKey = `retry-${correlationId}`;
  const payload: Record<string, unknown> = {
    intent_type: "intent.retry.demo.v1",
    correlation_id: correlationId,
    payload: {
      task: "sync_remote_inventory",
      target_system: "warehouse-api",
    },
  };
  if (toAgent) payload["to_agent"] = toAgent;

  console.log(`[agent]   to_agent=${toAgent ?? "(derived by server)"}`);
  console.log(`[agent]   from_agent=(derived from API key)`);
  console.log();

  const createdFirst = await client.createIntent(payload, { correlationId, idempotencyKey });
  const createdSecond = await client.createIntent(payload, { correlationId, idempotencyKey });
  const intentId = String(createdFirst.intent_id);
  console.log(`[create] intent_id=${intentId}`);
  console.log(`  status     ${String(createdFirst.status ?? "unknown")}`);
  console.log(`  🎾 ball at  retry-worker (executing, may fail transiently)`);
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
      );
      console.log(
        `[controls] applied=${String(controls.applied ?? "unknown")} policy_generation=${String(controls.policy_generation ?? "unknown")}`,
      );
      console.log(`  🎾 ball at  retry-worker (backing off, attempt ${attempts}/${maxAttempts})`);
      await new Promise((resolve) => setTimeout(resolve, Math.max(0, delaySeconds) * 1000));
    }
  }

  if (externalResult) {
    console.log(`  🎾 ball at  orchestrator (all attempts done, resolving COMPLETED)`);
    const resolved = await client.resolveIntent(intentId, {
      status: "COMPLETED",
      result: {
        attempts,
        retry_backoff_seconds: delays,
        external_result: externalResult,
      },
    });
    const event = (resolved.event ?? {}) as Record<string, unknown>;
    const terminalStatus = String(event.status ?? "COMPLETED");
    console.log(`[resolve] status=${terminalStatus}`);
    console.log(`  🎾 ball at  🟢 done  — terminal state ${terminalStatus}`);
  } else {
    console.log(`  🎾 ball at  orchestrator (max attempts reached, resolving FAILED)`);
    const failed = await client.resolveIntent(intentId, {
      status: "FAILED",
      error: {
        code: "max_attempts_exceeded",
        attempts,
        retry_backoff_seconds: delays,
      },
    });
    const event = (failed.event ?? {}) as Record<string, unknown>;
    const terminalStatus = String(event.status ?? "FAILED");
    console.log(`[resolve] status=${terminalStatus}`);
    console.log(`  🎾 ball at  🟢 done  — terminal state ${terminalStatus}`);
  }

  const finalIntent = ((await client.getIntent(intentId)).intent ?? {}) as Record<string, unknown>;
  console.log();
  console.log(`[done]   intent_id=${intentId}`);
  console.log(`         status=${String(finalIntent.status ?? "unknown")}  lifecycle_status=${String(finalIntent.lifecycle_status ?? "unknown")}`);
  console.log();
  console.log("  Explore via CLI:");
  console.log(`    axme intents get ${intentId}`);
  console.log(`    axme intents watch ${intentId}`);
}

main().catch((error) => {
  console.error("[error]", error);
  process.exit(1);
});
