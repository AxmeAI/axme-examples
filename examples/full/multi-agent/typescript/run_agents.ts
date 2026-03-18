/**
 * Run both agents for the full multi-agent scenario (TypeScript).
 *
 * Starts compliance-checker-agent and risk-assessment-agent concurrently.
 *
 * Usage:
 *   npx tsx examples/full/multi-agent/run_agents.ts
 *
 * Then in another terminal:
 *   axme scenarios apply examples/full/multi-agent/scenario.json --watch
 */
import { spawn, ChildProcess } from "node:child_process";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const WORKSPACE = join(dirname(__filename), "..", "..", "..");
const AGENT_CREDS = join(homedir(), ".config", "axme", "scenario-agents.json");

const AGENTS = [
  { nameFragment: "compliance-checker", script: join(WORKSPACE, "examples", "delivery", "stream", "agent.ts"), address: "compliance-checker-agent" },
  { nameFragment: "risk-assessment", script: join(WORKSPACE, "examples", "internal", "notification", "agent.ts"), address: "risk-assessment-agent" },
];

function loadApiKey(nameFragment: string): string {
  try {
    const data = JSON.parse(readFileSync(AGENT_CREDS, "utf-8"));
    for (const entry of data.agents ?? []) {
      if (String(entry.address ?? "").includes(nameFragment)) return String(entry.api_key ?? "");
    }
  } catch { /* ignore */ }
  return "";
}

console.log("Starting agents for full/multi-agent scenario...\n");

const procs: ChildProcess[] = [];

for (const agent of AGENTS) {
  let key = loadApiKey(agent.nameFragment);
  if (!key) key = process.env.AXME_API_KEY ?? "";
  if (!key) {
    console.warn(`[warn] no API key found for '${agent.nameFragment}'; run 'axme scenarios apply ... --watch' first`);
  }

  const env = { ...process.env, AXME_AGENT_ADDRESS: agent.address };
  if (key) env.AXME_API_KEY = key;

  console.log(`[agent]  ${agent.address} — ${agent.script.split("/").pop()}`);
  const proc = spawn("npx", ["tsx", agent.script], { env, stdio: "inherit" });
  procs.push(proc);
}

console.log("\nBoth agents running. Press Ctrl+C to stop.\n");

process.on("SIGINT", () => {
  console.log("\nShutting down agents...");
  for (const proc of procs) proc.kill("SIGTERM");
  process.exit(0);
});

await Promise.all(procs.map(p => new Promise(r => p.on("exit", r))));
