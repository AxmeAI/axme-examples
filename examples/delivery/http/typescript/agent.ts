/**
 * Order Processing Agent — HTTP delivery binding (TypeScript).
 *
 * Delivery: http  (AXME POSTs intent to callback_url)
 * The agent runs an HTTP server. AXME delivers intents by POSTing to the callback URL.
 *
 * Run:
 *   export AXME_API_KEY=<your-api-key>
 *   export CALLBACK_URL=https://<your-public-url>/intent
 *   export PORT=8080
 *   npx tsx examples/delivery/http/agent.ts
 */
import { createServer } from "node:http";
import { createHmac, timingSafeEqual } from "node:crypto";
import { AxmeClient } from "@axme/axme";

const AXME_BASE_URL = process.env.AXME_BASE_URL ?? "https://api.cloud.axme.ai";
const AXME_API_KEY = process.env.AXME_API_KEY ?? "";
const AXME_AGENT_ADDRESS = process.env.AXME_AGENT_ADDRESS ?? "http-order-processor";
const CALLBACK_URL = process.env.CALLBACK_URL ?? "";
const PORT = parseInt(process.env.PORT ?? "8080", 10);
const AXME_WEBHOOK_SECRET = process.env.AXME_WEBHOOK_SECRET ?? "";

if (!AXME_API_KEY) { console.error("AXME_API_KEY is required"); process.exit(1); }

const client = new AxmeClient({ apiKey: AXME_API_KEY, baseUrl: AXME_BASE_URL });

// --- Business logic ---
const SUPPORTED_CURRENCIES = new Set(["USD", "EUR", "GBP", "JPY"]);

function processOrder(payload: Record<string, unknown>): Record<string, unknown> {
  const eventType = String(payload.event_type ?? "");
  const orderId = String(payload.order_id ?? "");
  const amount = Number(payload.amount ?? 0);
  const currency = String(payload.currency ?? "");

  if (eventType !== "order.placed") return { action: "fail", reason: `unexpected event_type='${eventType}'` };
  if (!orderId) return { action: "fail", reason: "order_id is required" };
  if (!SUPPORTED_CURRENCIES.has(currency)) return { action: "fail", reason: `unsupported currency='${currency}'` };
  if (amount < 0.01 || amount > 1_000_000) return { action: "fail", reason: `amount=${amount} out of range` };

  const trackingId = `TRK-${orderId.toUpperCase()}-${String(Math.abs(hashCode(orderId)) % 100000).padStart(5, "0")}`;
  return { action: "complete", order_id: orderId, tracking_id: trackingId, status: "accepted", currency, amount };
}

function hashCode(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return h;
}

// --- HMAC verification ---
function verifySignature(body: Buffer, sig: string): boolean {
  if (!AXME_WEBHOOK_SECRET) return true;
  if (!sig) return false;
  const expected = createHmac("sha256", AXME_WEBHOOK_SECRET).update(body).digest("hex");
  const received = sig.replace("sha256=", "");
  try {
    return timingSafeEqual(Buffer.from(expected), Buffer.from(received));
  } catch { return false; }
}

// --- HTTP server ---
async function handleIntentAsync(intentId: string): Promise<void> {
  console.log(`received intent ${intentId} via http callback`);
  let intent: Record<string, unknown>;
  try { intent = await client.getIntent(intentId); } catch (e) { console.error(`get_intent(${intentId}) failed:`, e); return; }

  const payload = (intent.payload ?? {}) as Record<string, unknown>;
  const result = processOrder(payload);
  const action = result.action;
  delete result.action;

  try {
    await client.resumeIntent(intentId, { action, ...result }, { ownerAgent: AXME_AGENT_ADDRESS });
    console.log(`resumed ${intentId}  action=${action}`);
  } catch (e) { console.error(`resume_intent(${intentId}) failed:`, e); }
}

const server = createServer((req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end('{"status":"ok"}');
    return;
  }
  if (req.method !== "POST" || req.url !== "/intent") {
    res.writeHead(404); res.end(); return;
  }

  const chunks: Buffer[] = [];
  req.on("data", (c: Buffer) => chunks.push(c));
  req.on("end", () => {
    const body = Buffer.concat(chunks);
    if (!verifySignature(body, String(req.headers["x-axme-signature"] ?? ""))) {
      res.writeHead(401); res.end(); return;
    }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end('{"ack":true}');

    try {
      const envelope = JSON.parse(body.toString()) as Record<string, unknown>;
      const intentId = String(envelope.intent_id ?? "");
      if (intentId) handleIntentAsync(intentId).catch(e => console.error("async handler error:", e));
    } catch (e) { console.error("failed to parse delivery body:", e); }
  });
});

console.log(`http-order-processor starting  address=${AXME_AGENT_ADDRESS}  binding=http  port=${PORT}`);
console.log(`AXME will POST intents to: ${CALLBACK_URL || `http://localhost:${PORT}/intent`}`);
server.listen(PORT);
