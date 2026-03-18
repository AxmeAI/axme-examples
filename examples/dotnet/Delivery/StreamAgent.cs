using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
var apiKey = SseHelper.Env("AXME_API_KEY");
var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "compliance-checker-agent");
if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
Console.WriteLine($"compliance-checker-agent starting  address={addr}  binding=stream");

string[] blocked = ["production"];
string[] riskBackup = ["high", "critical"];
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

            var changeId = SseHelper.Str(p, "change_id", "?");
            var env = SseHelper.Str(p, "environment");
            var risk = SseHelper.Str(p, "risk_level", "low");
            var backup = p["backup_confirmed"]?.GetValue<bool>() == true;

            bool passed; string reason;
            if (blocked.Contains(env)) { passed = false; reason = $"{changeId}: production changes require manual approval"; }
            else if (riskBackup.Contains(risk) && !backup) { passed = false; reason = $"{changeId}: risk_level={risk} requires backup_confirmed=true"; }
            else { passed = true; reason = $"{changeId}: compliance checks passed"; }

            var res = new JsonObject { ["action"] = passed ? "complete" : "fail", ["passed"] = passed, ["reason"] = reason };
            if (passed) res["checked_fields"] = new JsonArray("environment", "risk_level", "backup_confirmed");
            await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
            Console.WriteLine($"resumed {id} (passed={passed})");
        }
    }
    catch (Exception ex) { Console.Error.WriteLine($"stream error: {ex.Message}"); await Task.Delay(2000); }
}
