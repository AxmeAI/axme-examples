using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
var apiKey = SseHelper.Env("AXME_API_KEY");
var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "access-policy-checker");
if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
Console.WriteLine($"access-policy-checker starting  address={addr}");
string[] allowed = ["READ", "READ_WRITE"]; string[] piiBlocked = ["READ_WRITE", "WRITE", "ADMIN"];
string[] signoff = ["prod-analytics-db", "prod-customer-db", "prod-payments-db"];
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

            var access = SseHelper.Str(p, "access_type").ToUpper();
            var requestor = SseHelper.Str(p, "requestor");
            var pii = p["pii_fields"]?.GetValue<bool>() == true;
            var checks = new List<string>(); var violations = new List<string>();

            if (allowed.Contains(access)) checks.Add("access ok"); else violations.Add("access not allowed");
            if (!string.IsNullOrEmpty(requestor)) checks.Add("requestor present"); else violations.Add("requestor missing");
            if (pii && piiBlocked.Contains(access)) violations.Add("PII write blocked");
            else if (pii) checks.Add("PII read ok"); else checks.Add("no PII");

            var ok = violations.Count == 0;
            var res = new JsonObject { ["action"] = ok ? "complete" : "fail", ["policy_passed"] = ok,
                ["passed_checks"] = new JsonArray(checks.Select(s => (JsonNode)JsonValue.Create(s)!).ToArray()),
                ["violations"] = new JsonArray(violations.Select(s => (JsonNode)JsonValue.Create(s)!).ToArray()) };
            if (ok) res["requires_human_signoff"] = signoff.Contains(SseHelper.Str(p, "resource"));
            await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
            Console.WriteLine($"resumed {id} (passed={ok})");
        }
    }
    catch { await Task.Delay(2000); }
}
