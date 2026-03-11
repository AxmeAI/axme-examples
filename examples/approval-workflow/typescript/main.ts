/**
 * Approval workflow: 4 scenarios (change management, finance, access management, AI oversight)
 *
 * Each scenario uses the same two-threaded flow:
 *   - main (async):  creates intent, drives automated steps, handles human input
 *   - worker:        calls resumeIntent on behalf of each automated reviewer
 *
 * Ball tracking (printed during run):
 *   ⚙  [process-agent]  — automated reviewer holds the ball
 *   👤 [human]           — human reviewer holds the ball
 *   🟢 [done]            — intent completed
 *
 * Usage:
 *   export AXME_API_KEY="axme_sa_..."
 *   export AXME_TO_AGENT="agent://acme-corp/production/approver"   # optional
 *   SCENARIO=2 npx ts-node main.ts
 */

import { config as loadEnv } from "dotenv";
import * as readline from "node:readline/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AxmeClient } from "@axme/axme/dist/src/index.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

loadEnv({ path: path.resolve(__dirname, "..", ".env") });

// ---------------------------------------------------------------------------
// Scenarios
// ---------------------------------------------------------------------------

interface AutoStep {
  actor:         string;
  label:         string;
  reviewing:     string;
  approved:      string;
  waitingReason: string;
}

interface Scenario {
  title:              string;
  summary:            string;
  intentType:         string;
  autoSteps:          AutoStep[];
  humanRole:          string;
  humanLabel:         string;
  humanWaitingReason: string;
}

const SCENARIOS: Record<string, Scenario> = {
  "1": {
    title:      "nginx config rollout → prod-cluster-eu",
    summary:    "Update nginx config on prod-cluster-eu (change #CHG-4821)",
    intentType: "intent.approval.change_mgmt.v1",
    autoSteps: [
      {
        actor:         "process:change-validator",
        label:         "change-validator",
        reviewing:     "verifying maintenance window and rollback plan...",
        approved:      "maintenance window confirmed, rollback plan verified",
        waitingReason: "WAITING_FOR_AGENT",
      },
      {
        actor:         "process:impact-assessor",
        label:         "impact-assessor",
        reviewing:     "assessing blast radius and service dependencies...",
        approved:      "blast radius: low, zero downtime deployment confirmed",
        waitingReason: "WAITING_FOR_AGENT",
      },
    ],
    humanRole:          "Change Advisory Board (CAB)",
    humanLabel:         "CAB",
    humanWaitingReason: "WAITING_FOR_HUMAN",
  },
  "2": {
    title:      "$47,500 cloud infrastructure budget — Q2 expansion",
    summary:    "Budget approval request: $47,500 cloud infrastructure Q2 expansion (BUD-2024-Q2-EU)",
    intentType: "intent.approval.finance.v1",
    autoSteps: [
      {
        actor:         "process:budget-validator",
        label:         "budget-validator",
        reviewing:     "validating budget envelope against Q2 allocation...",
        approved:      "within Q2 envelope, 12% headroom remaining",
        waitingReason: "WAITING_FOR_AGENT",
      },
      {
        actor:         "process:cost-estimator",
        label:         "cost-estimator",
        reviewing:     "cross-checking vendor quotes and 12-month TCO...",
        approved:      "3 vendor quotes validated, TCO within 5% of estimate",
        waitingReason: "WAITING_FOR_AGENT",
      },
    ],
    humanRole:          "CFO / Finance Committee",
    humanLabel:         "CFO",
    humanWaitingReason: "WAITING_FOR_HUMAN",
  },
  "3": {
    title:      "READ access to prod-db-eu-west-1 for svc:data-pipeline",
    summary:    "Access request: READ on prod-db-eu-west-1 for svc:data-pipeline (ITSM-ACCESS-8821)",
    intentType: "intent.approval.access_mgmt.v1",
    autoSteps: [
      {
        actor:         "process:access-policy-checker",
        label:         "access-policy-checker",
        reviewing:     "verifying service identity and least-privilege policy...",
        approved:      "service identity verified, READ-only scope within policy",
        waitingReason: "WAITING_FOR_AGENT",
      },
      {
        actor:         "process:risk-assessor",
        label:         "risk-assessor",
        reviewing:     "evaluating data sensitivity and audit trail coverage...",
        approved:      "PII fields excluded, audit logging active on target DB",
        waitingReason: "WAITING_FOR_AGENT",
      },
    ],
    humanRole:          "Security Officer / DBA",
    humanLabel:         "Security Officer",
    humanWaitingReason: "WAITING_FOR_HUMAN",
  },
  "4": {
    title:      "AI agent action: send contract to client (Acme Corp, $120k)",
    summary:    "AI agent requests permission to send $120k contract to Acme Corp (CONTRACT-AC-2024-001)",
    intentType: "intent.approval.ai_oversight.v1",
    autoSteps: [
      {
        actor:         "process:contract-validator",
        label:         "contract-validator",
        reviewing:     "validating contract terms, signatures and entity details...",
        approved:      "contract terms valid, entities match CRM records",
        waitingReason: "WAITING_FOR_AGENT",
      },
      {
        actor:         "process:compliance-checker",
        label:         "compliance-checker",
        reviewing:     "running compliance checks (AML, sanctions, jurisdiction)...",
        approved:      "AML clear, no sanctions hits, jurisdiction confirmed",
        waitingReason: "WAITING_FOR_AGENT",
      },
    ],
    humanRole:          "Account Executive / Legal",
    humanLabel:         "Account Executive",
    humanWaitingReason: "WAITING_FOR_HUMAN",
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
    throw new Error(
      `${name} is not set. Run 'axme login' to sign in, then:\n` +
      `  export ${name}=$(axme context show --show-key --json | jq -r .api_key)`,
    );
  }
  return value;
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

const WAITING_REASON_LABEL: Record<string, string> = {
  WAITING_FOR_HUMAN: "waiting for human",
  WAITING_FOR_AGENT: "waiting for agent",
  WAITING_FOR_TOOL:  "waiting for tool",
  WAITING_FOR_TIME:  "waiting for time",
};

function formatStatus(status: string, waitingReason?: string): string {
  if (status === "WAITING" && waitingReason) {
    const label = WAITING_REASON_LABEL[waitingReason] ?? waitingReason.toLowerCase();
    return `WAITING  (${label})`;
  }
  return status;
}

function printBall(holder: string, note?: string): void {
  const suffix = note ? `  — ${note}` : "";
  console.log(`  🎾 ball at  ${holder}${suffix}`);
}

function printStatusLine(prev: string | undefined, status: string, waitingReason?: string): string {
  const current = formatStatus(status, waitingReason);
  if (prev === undefined) {
    console.log(`  status     ${current}`);
  } else if (prev.split(" ")[0] !== current.split(" ")[0]) {
    console.log(`  status     ${prev} → ${current}`);
  }
  return current;
}

async function pickScenario(): Promise<Scenario> {
  const envScenario = (process.env["SCENARIO"] ?? "").trim();
  if (envScenario && SCENARIOS[envScenario]) {
    return SCENARIOS[envScenario]!;
  }

  console.log();
  console.log("  Select a scenario:");
  console.log();
  for (const [key, s] of Object.entries(SCENARIOS)) {
    console.log(`    ${key}.  ${s.title}`);
  }
  console.log();

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    while (true) {
      const choice = (await rl.question("  Enter number (1–4): ")).trim();
      if (SCENARIOS[choice]) {
        return SCENARIOS[choice]!;
      }
      console.log("  Please enter 1, 2, 3, or 4.");
    }
  } finally {
    rl.close();
  }
}

// ---------------------------------------------------------------------------
// Approver worker
// ---------------------------------------------------------------------------

interface ApprovalTask {
  intentId:        string;
  stepLabel:       string;
  actor:           string;
  reason:          string;
  reviewDelayMs:   number;
  humanInputResolve?: () => void;
  resolve:         () => void;
  reject:          (e: unknown) => void;
}

function runApproverWorker(
  client: AxmeClient,
  getTask: () => Promise<ApprovalTask | null>,
): void {
  (async () => {
    while (true) {
      const task = await getTask();
      if (!task) break;
      try {
        if (task.humanInputResolve === undefined) {
          await sleep(task.reviewDelayMs);
        }
        // wait for human_input_resolve to be called externally (set later)
        if (task.humanInputResolve !== undefined) {
          await new Promise<void>((res) => {
            (task as any)._waitForHuman = res;
          });
        }
        await client.resumeIntent(
          task.intentId,
          {
            approve_current_step: true,
            reason:               task.reason,
            actor:                task.actor,
          },
        );
        task.resolve();
      } catch (err) {
        task.reject(err);
      }
    }
  })();
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const baseUrl    = (process.env["AXME_BASE_URL"] ?? "https://api.cloud.axme.ai").trim();
  const apiKey     = requireEnv("AXME_API_KEY");
  const actorToken = (process.env["AXME_ACTOR_TOKEN"] ?? "").trim() || undefined;
  let   toAgent    = (process.env["AXME_TO_AGENT"] ?? "").trim() || undefined;

  const scenario = await pickScenario();
  const autoSteps = scenario.autoSteps;
  const nSteps    = autoSteps.length + 1;

  const client = new AxmeClient({ baseUrl, apiKey, actorToken });

  console.log();
  console.log(`[scenario]  ${scenario.title}`);
  console.log(`[summary]   ${scenario.summary}`);
  console.log();

  // ── Resolve to_agent from registry if not set ────────────────────────────
  if (!toAgent) {
    const orgId       = (process.env["AXME_ORG_ID"] ?? "").trim() || undefined;
    const workspaceId = (process.env["AXME_WORKSPACE_ID"] ?? "").trim() || undefined;
    if (orgId && workspaceId) {
      try {
        const agentsResp = await client.listAgents({ orgId, workspaceId });
        const agents     = Array.isArray(agentsResp.agents) ? agentsResp.agents : [];
        if (agents.length > 0) {
          toAgent = String((agents[0] as Record<string, unknown>).address ?? "");
        }
      } catch {
        // silently fall through
      }
    }
    if (!toAgent) {
      console.log(
        "[hint]  AXME_TO_AGENT not set. Set it to the agent address that should receive\n" +
        "        this intent, e.g.:\n" +
        "          export AXME_TO_AGENT=agent://acme-corp/production/approver\n" +
        "        Proceeding without to_agent (server may reject or route internally).\n",
      );
    }
  }

  console.log(`[agent]     to_agent=${toAgent ?? "(not set, derived by server)"}`);
  console.log(`[agent]     from_agent=(derived from API key)`);
  console.log(`[steps]     ${nSteps} approval steps: ${autoSteps.length} automated + 1 human (${scenario.humanLabel})`);
  console.log();

  const correlationId  = crypto.randomUUID();
  const idempotencyKey = `approval-${correlationId}`;

  const intentPayload: Record<string, unknown> = {
    intent_type:    scenario.intentType,
    correlation_id: correlationId,
    payload: {
      request_id:    `req-${correlationId.slice(0, 8)}`,
      summary:       scenario.summary,
      approval_mode: "manual",
    },
  };
  if (toAgent) {
    intentPayload["to_agent"] = toAgent;
  }

  // ── Task queue for approver worker ───────────────────────────────────────
  type TaskOrNull = ApprovalTask | null;
  let nextTaskResolve: ((t: TaskOrNull) => void) | null = null;
  const taskQueue: TaskOrNull[] = [];

  function enqueueTask(t: TaskOrNull): void {
    if (nextTaskResolve) {
      const res  = nextTaskResolve;
      nextTaskResolve = null;
      res(t);
    } else {
      taskQueue.push(t);
    }
  }

  async function getTask(): Promise<TaskOrNull> {
    if (taskQueue.length > 0) {
      return taskQueue.shift()!;
    }
    return new Promise<TaskOrNull>((res) => {
      nextTaskResolve = res;
    });
  }

  runApproverWorker(client, getTask);

  // ── Create intent ─────────────────────────────────────────────────────────
  const created   = await client.createIntent(intentPayload, { correlationId, idempotencyKey });
  const intentId  = String(created.intent_id);
  const initStat  = String(created.status ?? "");
  console.log(`[create]    intent_id=${intentId}`);
  let lastStatus = printStatusLine(undefined, initStat);
  printBall("requester (this process)");

  // ── Automated steps ───────────────────────────────────────────────────────
  for (let i = 0; i < autoSteps.length; i++) {
    const step    = autoSteps[i]!;
    const stepNum = i + 1;

    console.log();
    console.log(`[step ${stepNum}/${nSteps}]  ⚙  ${step.label} — ${step.reviewing}`);
    printBall(`process-agent:${step.label}`);

    await new Promise<void>((resolve, reject) => {
      const task: ApprovalTask = {
        intentId,
        stepLabel:     `step ${stepNum}/${nSteps}`,
        actor:         step.actor,
        reason:        `${step.actor} approved — ${step.approved}`,
        reviewDelayMs: 2000,
        resolve,
        reject,
      };
      enqueueTask(task);
    });

    const updated   = await client.getIntent(intentId);
    const updData   = (updated.intent ?? {}) as Record<string, unknown>;
    const curStatus = String(updData.lifecycle_status ?? updData.status ?? lastStatus);
    lastStatus      = printStatusLine(lastStatus, curStatus);

    console.log(`  [approved] ${step.label}  ✓  ${step.approved}`);
    printBall("requester (this process)", "moving to next step");
    await sleep(500);
  }

  // ── Human approval step ───────────────────────────────────────────────────
  const humanStep = autoSteps.length + 1;
  console.log();
  console.log(`[step ${humanStep}/${nSteps}]  👤  ${scenario.humanRole} — waiting for sign-off`);
  printBall(`human:${scenario.humanLabel}`);
  console.log();
  console.log(`           Intent is paused. You are acting as ${scenario.humanRole}.`);
  console.log(`           Press Enter to approve, or Ctrl+C to cancel.`);
  console.log();

  let humanWorkerTrigger: (() => void) | null = null;

  const humanTaskPromise = new Promise<void>((resolve, reject) => {
    const task: ApprovalTask = {
      intentId,
      stepLabel:          `step ${humanStep}/${nSteps}`,
      actor:              `human:${scenario.humanLabel}`,
      reason:             `approved by ${scenario.humanRole}`,
      reviewDelayMs:      0,
      humanInputResolve:  () => { /* marker */ },
      resolve,
      reject,
    };
    // We'll trigger the worker after user confirms
    (task as any)._waitForHuman = null;
    humanWorkerTrigger = () => {
      if ((task as any)._waitForHuman) {
        (task as any)._waitForHuman();
      }
    };
    enqueueTask(task);
  });

  // Wait for user confirmation
  const rl2 = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    await rl2.question("           > ");
  } catch {
    console.log("\n[cancelled]  approval cancelled");
    enqueueTask(null);
    rl2.close();
    return;
  } finally {
    rl2.close();
  }

  console.log();
  console.log(`[approved]  ${scenario.humanRole} confirmed — resuming intent`);
  printBall("requester (this process)", "human approved, calling resume");
  if (humanWorkerTrigger) humanWorkerTrigger();

  await humanTaskPromise;

  // ── Resolve ───────────────────────────────────────────────────────────────
  await client.resolveIntent(intentId, {
    status: "COMPLETED",
    result: {
      approval_result: "approved",
      approved_by:     scenario.humanRole,
      summary:         scenario.summary,
    },
  });
  printBall("server", "resolve_intent called → terminal event incoming");

  // ── Final state ───────────────────────────────────────────────────────────
  await sleep(1000);
  const finalIntent = await client.getIntent(intentId);
  const finalData   = (finalIntent.intent ?? {}) as Record<string, unknown>;
  const finalStatus = String(finalData.lifecycle_status ?? finalData.status ?? lastStatus);
  lastStatus = printStatusLine(lastStatus, finalStatus);

  if (["COMPLETED", "FAILED", "CANCELED"].includes(finalStatus)) {
    printBall("🟢 done", `intent reached terminal state ${finalStatus}`);
  }

  // ── Lifecycle events ──────────────────────────────────────────────────────
  const listed = await client.listIntentEvents(intentId);
  const events = (listed.events ?? []) as Array<Record<string, unknown>>;
  if (events.length > 0) {
    console.log();
    console.log("[lifecycle] events:");
    for (const ev of events) {
      const seq     = ev["seq"] ?? 0;
      const evStat  = String(ev["status"] ?? "unknown");
      const actor   = String(ev["actor_id"] ?? ev["actor"] ?? "system");
      const waiting = ev["waiting_reason"] ? ` waiting_reason=${String(ev["waiting_reason"])}` : "";
      console.log(`  seq=${String(seq)}  status=${evStat}  actor=${actor}${waiting}`);
    }
  }

  console.log();
  console.log(`[done]    intent_id=${intentId}  status=${finalStatus.split(" ")[0]}`);
  console.log();
  console.log("  Explore via CLI:");
  console.log(`    axme intents get ${intentId}`);
  console.log(`    axme intents watch ${intentId}   # replay lifecycle events`);
  console.log( "    axme quota show");

  enqueueTask(null);
}

main().catch((error: unknown) => {
  console.error("[error]", error);
  process.exit(1);
});
