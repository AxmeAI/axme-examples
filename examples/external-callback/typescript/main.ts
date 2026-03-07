import { config as loadEnv } from "dotenv";
import http from "node:http";
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

function asBool(name: string, fallback: boolean): boolean {
  const raw = (process.env[name] ?? "").trim().toLowerCase();
  if (!raw) {
    return fallback;
  }
  return ["1", "true", "yes", "on"].includes(raw);
}

async function simulateCallback(callbackUrl: string, delaySeconds: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, Math.max(0, delaySeconds) * 1000));
  const payload = {
    provider: "billing-gateway",
    callback_status: "approved",
    external_reference: `ext-${crypto.randomUUID().slice(0, 8)}`,
    amount_cents: 4999,
  };
  await fetch(callbackUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function main(): Promise<void> {
  const baseUrl = (process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai").trim();
  const apiKey = requireEnv("AXME_API_KEY");
  const actorToken = (process.env.AXME_ACTOR_TOKEN ?? "").trim() || undefined;
  const fromAgent = (process.env.AXME_FROM_AGENT ?? "agent://examples/orchestrator").trim();
  const toAgent = (process.env.AXME_TO_AGENT ?? "agent://examples/external-worker").trim();
  const ownerAgent = (process.env.AXME_OWNER_AGENT ?? fromAgent).trim();
  const callbackHost = (process.env.AXME_CALLBACK_HOST ?? "127.0.0.1").trim();
  const callbackPort = asInt("AXME_CALLBACK_PORT", 8787);
  const callbackTimeoutSeconds = asInt("AXME_CALLBACK_TIMEOUT_SECONDS", 30);
  const simulate = asBool("AXME_SIMULATE_CALLBACK", true);

  const callbackPath = "/external/callback";
  const callbackUrl = `http://${callbackHost}:${callbackPort}${callbackPath}`;
  console.log(`[callback] listening on ${callbackUrl}`);

  const callbackPayloadPromise = new Promise<Record<string, unknown>>((resolve, reject) => {
    const timeout = setTimeout(
      () => reject(new Error(`timed out waiting for callback after ${callbackTimeoutSeconds}s`)),
      callbackTimeoutSeconds * 1000,
    );
    const server = http.createServer((req, res) => {
      if (req.method !== "POST" || req.url !== callbackPath) {
        res.writeHead(404).end();
        return;
      }
      const chunks: Buffer[] = [];
      req.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
      req.on("end", () => {
        clearTimeout(timeout);
        let parsed: unknown = {};
        try {
          parsed = JSON.parse(Buffer.concat(chunks).toString("utf-8"));
        } catch {
          parsed = { raw: Buffer.concat(chunks).toString("utf-8") };
        }
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
        server.close();
        resolve((parsed ?? {}) as Record<string, unknown>);
      });
    });
    server.on("error", reject);
    server.listen(callbackPort, callbackHost);
  });

  if (simulate) {
    console.log("[callback] simulation enabled; callback will be posted automatically.");
    void simulateCallback(callbackUrl, 2);
  }

  const client = new AxmeClient({ baseUrl, apiKey, actorToken });
  const correlationId = crypto.randomUUID();
  const idempotencyKey = `external-callback-${correlationId}`;
  const payload = {
    intent_type: "intent.external_callback.demo.v1",
    correlation_id: correlationId,
    from_agent: fromAgent,
    to_agent: toAgent,
    payload: {
      operation: "capture_payment",
      order_id: `order-${correlationId.slice(0, 8)}`,
      callback_url: callbackUrl,
    },
  };

  const created = await client.createIntent(payload, { correlationId, idempotencyKey });
  const intentId = String(created.intent_id);
  console.log(`[create] intent_id=${intentId} status=${String(created.status ?? "unknown")}`);

  const callbackPayload = await callbackPayloadPromise;
  console.log(`[callback] received: ${JSON.stringify(callbackPayload)}`);

  const resumed = await client.resumeIntent(
    intentId,
    {
      approve_current_step: true,
      reason: "external callback received",
    },
    { ownerAgent },
  );
  console.log(`[resume] applied=${String(resumed.applied ?? "unknown")} policy_generation=${String(resumed.policy_generation ?? "unknown")}`);

  const resolved = await client.resolveIntent(intentId, {
    status: "COMPLETED",
    result: {
      source: "external_callback",
      callback_payload: callbackPayload,
    },
  });
  const event = (resolved.event ?? {}) as Record<string, unknown>;
  console.log(`[resolve] event_type=${String(event.event_type ?? "unknown")} status=${String(event.status ?? "unknown")}`);

  const finalIntent = ((await client.getIntent(intentId)).intent ?? {}) as Record<string, unknown>;
  console.log(
    `[final] intent_id=${intentId} status=${String(finalIntent.status ?? "unknown")} lifecycle_status=${String(finalIntent.lifecycle_status ?? "unknown")}`,
  );
}

main().catch((error) => {
  console.error("[error]", error);
  process.exit(1);
});
