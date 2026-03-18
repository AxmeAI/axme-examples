using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
var apiKey = SseHelper.Env("AXME_API_KEY");
var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "pre-approval-validator");
if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
Console.WriteLine($"pre-approval-validator starting  address={addr}");
string[] types = ["config_update", "dependency_update", "rollback", "hotfix"];
string[] risks = ["low", "medium", "high", "critical"];
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

            var cid = SseHelper.Str(p, "change_id", "?"); var ct = SseHelper.Str(p, "change_type");
            var rl = SseHelper.Str(p, "risk_level"); var svc = SseHelper.Str(p, "service");
            bool valid; string reason;
            if (string.IsNullOrEmpty(svc)) { valid = false; reason = $"{cid}: service required"; }
            else if (!types.Contains(ct)) { valid = false; reason = $"{cid}: change_type not allowed"; }
            else if (!risks.Contains(rl)) { valid = false; reason = $"{cid}: risk_level not valid"; }
            else { valid = true; reason = $"{cid}: pre-validation passed for {svc}"; }

            var res = new JsonObject { ["action"] = valid ? "complete" : "fail", ["valid"] = valid, ["reason"] = reason };
            await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
            Console.WriteLine($"resumed {id} (valid={valid})");
        }
    }
    catch { await Task.Delay(2000); }
}
