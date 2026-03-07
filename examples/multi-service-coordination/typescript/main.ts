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

async function createChildIntent(
  client: AxmeClient,
  options: {
    fromAgent: string;
    toAgent: string;
    serviceName: string;
    parentIntentId: string;
  },
): Promise<string> {
  const correlationId = crypto.randomUUID();
  const created = await client.createIntent(
    {
      intent_type: "intent.service_step.demo.v1",
      correlation_id: correlationId,
      from_agent: options.fromAgent,
      to_agent: options.toAgent,
      payload: {
        service: options.serviceName,
        parent_intent_id: options.parentIntentId,
        task: `run_${options.serviceName}_step`,
      },
    },
    {
      correlationId,
      idempotencyKey: `child-${options.serviceName}-${correlationId}`,
    },
  );
  return String(created.intent_id);
}

async function main(): Promise<void> {
  const baseUrl = (process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai").trim();
  const apiKey = requireEnv("AXME_API_KEY");
  const actorToken = (process.env.AXME_ACTOR_TOKEN ?? "").trim() || undefined;
  const fromAgent = (process.env.AXME_FROM_AGENT ?? "agent://examples/coordinator").trim();
  const ownerAgent = (process.env.AXME_OWNER_AGENT ?? fromAgent).trim();
  const parentToAgent = (process.env.AXME_PARENT_TO_AGENT ?? "agent://examples/orchestrator-runtime").trim();
  const serviceBAgent = (process.env.AXME_SERVICE_B_AGENT ?? "agent://examples/service-b").trim();
  const serviceCAgent = (process.env.AXME_SERVICE_C_AGENT ?? "agent://examples/service-c").trim();

  const client = new AxmeClient({ baseUrl, apiKey, actorToken });

  const parentCorrelationId = crypto.randomUUID();
  const parent = await client.createIntent(
    {
      intent_type: "intent.multi_service.demo.v1",
      correlation_id: parentCorrelationId,
      from_agent: fromAgent,
      to_agent: parentToAgent,
      payload: {
        operation: "provision_enterprise_workspace",
        steps: ["service_b", "service_c"],
      },
    },
    {
      correlationId: parentCorrelationId,
      idempotencyKey: `parent-${parentCorrelationId}`,
    },
  );
  const parentIntentId = String(parent.intent_id);
  console.log(`[parent:create] intent_id=${parentIntentId} status=${String(parent.status ?? "unknown")}`);

  const resumedParent = await client.resumeIntent(
    parentIntentId,
    { approve_current_step: true, reason: "start orchestration" },
    { ownerAgent },
  );
  console.log(
    `[parent:resume] applied=${String(resumedParent.applied ?? "unknown")} policy_generation=${String(resumedParent.policy_generation ?? "unknown")}`,
  );

  const childBId = await createChildIntent(client, {
    fromAgent,
    toAgent: serviceBAgent,
    serviceName: "service_b",
    parentIntentId,
  });
  const childCId = await createChildIntent(client, {
    fromAgent,
    toAgent: serviceCAgent,
    serviceName: "service_c",
    parentIntentId,
  });
  console.log(`[child:create] service_b_intent_id=${childBId}`);
  console.log(`[child:create] service_c_intent_id=${childCId}`);

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
  const parentEvent = (parentResolved.event ?? {}) as Record<string, unknown>;
  console.log(`[parent:resolve] status=${String(parentEvent.status ?? "unknown")}`);

  const finalParent = ((await client.getIntent(parentIntentId)).intent ?? {}) as Record<string, unknown>;
  console.log(
    `[final] parent_intent_id=${parentIntentId} status=${String(finalParent.status ?? "unknown")} lifecycle_status=${String(finalParent.lifecycle_status ?? "unknown")}`,
  );
}

main().catch((error) => {
  console.error("[error]", error);
  process.exit(1);
});
