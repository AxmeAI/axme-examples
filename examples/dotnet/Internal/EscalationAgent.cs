using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Internal;

public class EscalationAgent
{
    public static async Task Main(string[] args)
    {
        var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        var apiKey = SseHelper.Env("AXME_API_KEY");
        var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "incident-classifier-agent");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine($"incident-classifier starting  address={addr}");
        var sla = new Dictionary<string, int> { ["P1"] = 5, ["P2"] = 15, ["P3"] = 60, ["P4"] = 240 };
        string[] critical = ["api-gateway", "auth-service", "payments-processor"];
        var since = 0;

        while (true)
        {
            try
            {
                foreach (var d in await SseHelper.PollAgentStreamAsync(baseUrl, apiKey, addr, since))
                {
                    var id = SseHelper.Str(d, "intent_id");
                    if (d["seq"]?.GetValue<int>() is int seq) since = Math.Max(since, seq);
                    if (string.IsNullOrEmpty(id)) continue;
                    var intent = SseHelper.UnwrapIntent(await client.GetIntentAsync(id));
                    if (!SseHelper.IsActionable(intent)) continue;
                    var p = SseHelper.EffectivePayload(intent);

                    var sev = SseHelper.Str(p, "severity", "P3"); var svc = SseHelper.Str(p, "service");
                    var symptom = SseHelper.Str(p, "symptom");
                    var isCrit = critical.Contains(svc); var minutes = sla.GetValueOrDefault(sev, 60);
                    var affected = new List<string>(); if (!string.IsNullOrEmpty(svc)) affected.Add(svc); if (isCrit) affected.Add("downstream-dependents");
                    var esc = (sev is "P1" or "P2") && isCrit ? "on-call → team-lead → engineering-director" : sev is "P1" or "P2" ? "on-call → team-lead" : "on-call";

                    var res = new JsonObject { ["action"] = "complete", ["incident_id"] = SseHelper.Str(p, "incident_id", "?"),
                        ["severity"] = sev, ["is_critical_service"] = isCrit, ["sla_minutes"] = minutes,
                        ["affected_components"] = new JsonArray(affected.Select(a => (JsonNode)JsonValue.Create(a)!).ToArray()),
                        ["escalation_path"] = esc, ["has_error_rate_signal"] = symptom.Contains("error rate", StringComparison.OrdinalIgnoreCase) || symptom.Contains("5xx") };
                    await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
                    Console.WriteLine($"resumed {id}");
                }
            }
            catch { await Task.Delay(2000); }
        }
    }
}
