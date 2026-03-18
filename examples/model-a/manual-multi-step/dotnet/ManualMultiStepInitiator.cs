using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.ModelA;

public class ManualMultiStepInitiator
{
    private static async Task<string> WaitForDone(AxmeClient client, string intentId, int timeoutSec = 60)
    {
        var since = 0; var deadline = DateTime.UtcNow.AddSeconds(timeoutSec);
        while (DateTime.UtcNow < deadline)
        {
            var events = await client.ListIntentEventsAsync(intentId, since);
            foreach (var evt in events["events"]?.AsArray() ?? [])
            {
                var st = evt?["status"]?.ToString() ?? "";
                if (evt?["seq"]?.GetValue<int>() is int seq) since = Math.Max(since, seq);
                if (st is "COMPLETED" or "IN_PROGRESS" or "FAILED" or "CANCELED" or "TIMED_OUT") return st;
            }
            await Task.Delay(1000);
        }
        return "UNKNOWN";
    }

    public static async Task Main(string[] args)
    {
        var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        var apiKey = SseHelper.Env("AXME_API_KEY");
        var agent1 = SseHelper.Env("AXME_AGENT_1"); var agent2 = SseHelper.Env("AXME_AGENT_2");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }
        if (string.IsNullOrEmpty(agent1) || string.IsNullOrEmpty(agent2)) { Console.Error.WriteLine("AXME_AGENT_1 and AXME_AGENT_2 required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });

        var payload = new JsonObject { ["change_id"] = "CHG-MULTI-STEP-001", ["service"] = "api-gateway",
            ["version"] = "5.0.0", ["environment"] = "staging", ["change_type"] = "config_update",
            ["risk_level"] = "medium", ["risk_threshold"] = 30 };

        // Step 1
        Console.WriteLine($"STEP 1: compliance check → {agent1}");
        var c1 = await client.CreateIntentAsync(new JsonObject { ["intent_type"] = "intent.compliance.check.v1",
            ["from_agent"] = "initiator://manual-multi-step", ["to_agent"] = agent1,
            ["correlation_id"] = Guid.NewGuid().ToString(), ["payload"] = payload.DeepClone() });
        var s1id = c1["intent_id"]?.ToString() ?? "";
        Console.WriteLine($"step 1 intent: {s1id} — waiting...");
        var s1 = await WaitForDone(client, s1id);
        Console.WriteLine($"step 1 → {s1}");

        if (s1 is not ("COMPLETED" or "IN_PROGRESS")) { Console.Error.WriteLine($"step 1 failed ({s1}) — aborting"); return; }

        // Step 2
        Console.WriteLine($"STEP 2: risk assessment → {agent2}");
        var p2 = payload.DeepClone().AsObject();
        p2["compliance_result"] = "passed"; p2["compliance_intent_id"] = s1id;
        var c2 = await client.CreateIntentAsync(new JsonObject { ["intent_type"] = "intent.risk.assessment.v1",
            ["from_agent"] = "initiator://manual-multi-step", ["to_agent"] = agent2,
            ["correlation_id"] = Guid.NewGuid().ToString(), ["payload"] = p2 });
        var s2id = c2["intent_id"]?.ToString() ?? "";
        Console.WriteLine($"step 2 intent: {s2id} — waiting...");
        var s2 = await WaitForDone(client, s2id);
        Console.WriteLine($"step 2 → {s2}");

        Console.WriteLine("\n=== Manual Multi-Step Pipeline ===");
        Console.WriteLine($"  Step 1 (compliance): {s1}  id={s1id}");
        Console.WriteLine($"  Step 2 (risk):       {s2}  id={s2id}");
        var ok = s1 is "COMPLETED" or "IN_PROGRESS" && s2 is "COMPLETED" or "IN_PROGRESS";
        Console.WriteLine($"  Result: {(ok ? "ALL STEPS PASSED" : "PIPELINE FAILED")}");
    }
}
