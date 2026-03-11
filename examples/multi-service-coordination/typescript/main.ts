import { config as loadEnv } from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { AxmeClient } from "@axme/axme/dist/src/index.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

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

async function createChildIntent(
  client: AxmeClient,
  options: {
    toAgent?: string;
    serviceName: string;
    parentIntentId: string;
  },
): Promise<string> {
  const correlationId = crypto.randomUUID();
  const body: Record<string, unknown> = {
    intent_type: "intent.service_step.demo.v1",
    correlation_id: correlationId,
    payload: {
      service: options.serviceName,
      parent_intent_id: options.parentIntentId,
      task: `run_${options.serviceName}_step`,
    },
  };
  if (options.toAgent) body["to_agent"] = options.toAgent;
  const created = await client.createIntent(body, {
    correlationId,
    idempotencyKey: `child-${options.serviceName}-${correlationId}`,
  });
  return String(created.intent_id);
}

async function main(): Promise<void> {
  const baseUrl       = (process.env["AXME_BASE_URL"] ?? "https://api.cloud.axme.ai").trim();
  const apiKey        = requireEnv("AXME_API_KEY");
  const actorToken    = (process.env["AXME_ACTOR_TOKEN"] ?? "").trim() || undefined;
  // from_agent is derived by the server from the API key (no longer passed explicitly)
  const parentToAgent = (process.env["AXME_PARENT_TO_AGENT"] ?? "").trim() || undefined;
  const serviceBAgent = (process.env["AXME_SERVICE_B_AGENT"] ?? "").trim() || undefined;
  const serviceCAgent = (process.env["AXME_SERVICE_C_AGENT"] ?? "").trim() || undefined;

  const client = new AxmeClient({ baseUrl, apiKey, actorToken });

  console.log(`[agent]   parent_to_agent=${parentToAgent ?? "(derived by server)"}`);
  console.log(`[agent]   service_b_agent=${serviceBAgent ?? "(derived by server)"}`);
  console.log(`[agent]   service_c_agent=${serviceCAgent ?? "(derived by server)"}`);
  console.log(`[agent]   from_agent=(derived from API key)`);
  console.log();

  const parentCorrelationId = crypto.randomUUID();
  const parentBody: Record<string, unknown> = {
    intent_type: "intent.multi_service.demo.v1",
    correlation_id: parentCorrelationId,
    payload: {
      operation: "provision_enterprise_workspace",
      steps: ["service_b", "service_c"],
    },
  };
  if (parentToAgent) parentBody["to_agent"] = parentToAgent;

  const parent = await client.createIntent(parentBody, {
    correlationId: parentCorrelationId,
    idempotencyKey: `parent-${parentCorrelationId}`,
  });
  const parentIntentId = String(parent.intent_id);
  console.log(`[parent:create] intent_id=${parentIntentId}`);
  console.log(`  status     ${String(parent.status ?? "unknown")}`);
  console.log(`  🎾 ball at  orchestrator (starting sub-services)`);

  const resumedParent = await client.resumeIntent(
    parentIntentId,
    { approve_current_step: true, reason: "start orchestration" },
  );
  console.log(
    `[parent:resume] applied=${String(resumedParent.applied ?? "unknown")} policy_generation=${String(resumedParent.policy_generation ?? "unknown")}`,
  );

  const childBId = await createChildIntent(client, {
    toAgent: serviceBAgent,
    serviceName: "service_b",
    parentIntentId,
  });
  const childCId = await createChildIntent(client, {
    toAgent: serviceCAgent,
    serviceName: "service_c",
    parentIntentId,
  });
  console.log(`[child:create] service_b_intent_id=${childBId}`);
  console.log(`  🎾 ball at  service-b`);
  console.log(`[child:create] service_c_intent_id=${childCId}`);
  console.log(`  🎾 ball at  service-c (parallel)`);

  const childBResult = {
    service: "service_b",
    status: "done",
    artifact: `artifact-${crypto.randomUUID().slice(0, 8)}`,
  };
  const childCResult = {
    service: "service_c",
    status: "done",
    artifact: `artifact-${crypto.randomUUID().slice(0, 8)}`,
  };

  await client.resolveIntent(childBId, { status: "COMPLETED", result: childBResult });
  await client.resolveIntent(childCId, { status: "COMPLETED", result: childCResult });
  console.log("[child:resolve] service_b=COMPLETED service_c=COMPLETED");
  console.log(`  🎾 ball at  orchestrator (all children done, resolving parent)`);

  const parentResolved = await client.resolveIntent(parentIntentId, {
    status: "COMPLETED",
    result: {
      operation: "provision_enterprise_workspace",
      children: [
        { intent_id: childBId, result: childBResult },
        { intent_id: childCId, result: childCResult },
      ],
    },
  });
  const parentEvent    = (parentResolved.event ?? {}) as Record<string, unknown>;
  const terminalStatus = String(parentEvent.status ?? "COMPLETED");
  console.log(`[parent:resolve] status=${terminalStatus}`);
  console.log(`  🎾 ball at  🟢 done  — terminal state ${terminalStatus}`);

  const finalParent = ((await client.getIntent(parentIntentId)).intent ?? {}) as Record<string, unknown>;
  console.log();
  console.log(`[done]   parent_intent_id=${parentIntentId}`);
  console.log(`         status=${String(finalParent.status ?? "unknown")}  lifecycle_status=${String(finalParent.lifecycle_status ?? "unknown")}`);
  console.log();
  console.log("  Explore via CLI:");
  console.log(`    axme intents get ${parentIntentId}`);
  console.log(`    axme intents watch ${parentIntentId}`);
}

main().catch((error) => {
  console.error("[error]", error);
  process.exit(1);
});
