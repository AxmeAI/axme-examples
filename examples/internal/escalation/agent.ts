/**
 * Incident Classifier Agent — internal/escalation example (TypeScript).
 *
 * Classifies incidents by severity and affected components.
 * After classification, the workflow routes to on-call with reminders.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export AXME_AGENT_ADDRESS=incident-classifier-agent
 *   npx tsx examples/internal/escalation/agent.ts
 */
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "incident-classifier-agent";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

// --- Classification ---
const SEVERITY_SLA: Record<string, number> = { P1: 5, P2: 15, P3: 60, P4: 240 };
const CRITICAL_SERVICES = new Set(["api-gateway", "auth-service", "payments-processor"]);

function classifyIncident(payload: Record<string, unknown>): Record<string, unknown> {
  const incidentId = String(payload.incident_id ?? "?");
  const severity = String(payload.severity ?? "P3");
  const service = String(payload.service ?? "");
  const symptom = String(payload.symptom ?? "");
  const slaMinutes = SEVERITY_SLA[severity] ?? 60;
  const isCritical = CRITICAL_SERVICES.has(service);

  const affected = service ? [service] : [];
  if (isCritical) affected.push("downstream-dependents");

  let escalationPath: string;
  if (["P1", "P2"].includes(severity) && isCritical) escalationPath = "on-call → team-lead → engineering-director";
  else if (["P1", "P2"].includes(severity)) escalationPath = "on-call → team-lead";
  else escalationPath = "on-call";

  return {
    incident_id: incidentId, severity, is_critical_service: isCritical,
    has_error_rate_signal: /error rate|5xx/i.test(symptom),
    affected_components: affected, sla_minutes: slaMinutes,
    escalation_path: escalationPath,
    classification_note: `${incidentId}: ${severity} on '${service}' — SLA=${slaMinutes}m, escalation: ${escalationPath}`,
  };
}

// --- Agent loop ---
const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });
console.log(`incident-classifier starting  address=${AXME_AGENT_ADDRESS}  binding=stream`);

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
    const result = classifyIncident(effectivePayload);

    console.log(`classified incident ${intentId}: ${result.classification_note}`);

    try {
      await client.resumeIntent(intentId, { action: "complete", ...result }, { ownerAgent: AXME_AGENT_ADDRESS });
      console.log(`resumed intent ${intentId}`);
    } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
  }
} catch (e) {
  if ((e as Error).name !== "AbortError") throw e;
}
