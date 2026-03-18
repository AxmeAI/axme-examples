using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
var apiKey = SseHelper.Env("AXME_API_KEY");
var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "risk-assessment-agent");
if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
Console.WriteLine($"risk-assessment-agent starting  address={addr}");
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

            var ver = SseHelper.Str(p, "version", "0.0.0"); var env = SseHelper.Str(p, "environment");
            var cc = (int)(p["change_count"]?.GetValue<double>() ?? 0);
            var thresh = (int)(p["risk_threshold"]?.GetValue<double>() ?? 30);
            var parts = ver.Split('.'); int.TryParse(parts[0], out var major); var minor = parts.Length > 1 && int.TryParse(parts[1], out var m) ? m : 0;

            var score = 0; var factors = new List<string>();
            if (major >= 4) { score += 40; factors.Add($"major bump +40"); }
            else if (minor >= 5) { score += 15; factors.Add("minor bump +15"); }
            if (cc > 30) { score += 30; factors.Add($"high changes +30"); }
            if (env == "production") { score += 25; factors.Add("prod +25"); }
            else if (env is "staging" or "canary") { score += 10; factors.Add("staging +10"); }
            var level = score >= thresh ? "HIGH" : score >= thresh / 2 ? "MEDIUM" : "LOW";

            var res = new JsonObject { ["action"] = "complete", ["risk_score"] = score, ["risk_level"] = level,
                ["factors"] = new JsonArray(factors.Select(f => (JsonNode)JsonValue.Create(f)!).ToArray()) };
            await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
            Console.WriteLine($"resumed {id} (risk={level} score={score})");
        }
    }
    catch { await Task.Delay(2000); }
}
