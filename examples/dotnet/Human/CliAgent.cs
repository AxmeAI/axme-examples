using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Axme.Sdk;
using AxmeExamples;

var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
var apiKey = SseHelper.Env("AXME_API_KEY");
var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "deploy-readiness-checker");
if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
Console.WriteLine($"deploy-readiness-checker starting  address={addr}");
var semver = new Regex(@"^\d+\.\d+\.\d+$");
string[] envs = ["staging", "canary", "preview"];
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

            var ver = SseHelper.Str(p, "version"); var env = SseHelper.Str(p, "environment");
            var rb = SseHelper.Str(p, "rollback_tag"); var svc = SseHelper.Str(p, "service");
            var passed = new List<string>(); var fail = new List<string>();
            if (semver.IsMatch(ver)) passed.Add("version ok"); else fail.Add("version invalid");
            if (envs.Contains(env)) passed.Add("env ok"); else fail.Add("env not allowed");
            if (!string.IsNullOrEmpty(rb)) passed.Add("rollback set"); else fail.Add("rollback missing");
            if (!string.IsNullOrEmpty(svc)) passed.Add("service set"); else fail.Add("service empty");
            var ready = fail.Count == 0;

            var res = new JsonObject { ["action"] = ready ? "complete" : "fail", ["ready"] = ready,
                ["passed_checks"] = new JsonArray(passed.Select(s => (JsonNode)JsonValue.Create(s)!).ToArray()),
                ["failures"] = new JsonArray(fail.Select(s => (JsonNode)JsonValue.Create(s)!).ToArray()) };
            await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
            Console.WriteLine($"resumed {id} (ready={ready})");
        }
    }
    catch { await Task.Delay(2000); }
}
