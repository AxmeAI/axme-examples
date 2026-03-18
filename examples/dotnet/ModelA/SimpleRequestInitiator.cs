using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
var apiKey = SseHelper.Env("AXME_API_KEY");
var toAgent = SseHelper.Env("AXME_TO_AGENT");
if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }
if (string.IsNullOrEmpty(toAgent)) { Console.Error.WriteLine("AXME_TO_AGENT is required"); return; }

var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
Console.WriteLine($"creating intent to {toAgent} ...");

var created = await client.CreateIntentAsync(new JsonObject
{
    ["intent_type"] = "intent.compliance.check.v1",
    ["from_agent"] = "initiator://simple-request",
    ["to_agent"] = toAgent,
    ["payload"] = new JsonObject { ["change_id"] = "CHG-MODEL-A-001", ["service"] = "api-gateway",
        ["version"] = "4.0.0", ["environment"] = "staging", ["change_type"] = "config_update", ["risk_level"] = "low" }
});
var intentId = created["intent_id"]?.ToString() ?? "";
Console.WriteLine($"intent created: {intentId}\nwaiting for agent response...");

var since = 0;
var deadline = DateTime.UtcNow.AddSeconds(120);
while (DateTime.UtcNow < deadline)
{
    var events = await client.ListIntentEventsAsync(intentId, since);
    foreach (var evt in events["events"]?.AsArray() ?? [])
    {
        var status = evt?["status"]?.ToString() ?? "";
        if (evt?["seq"]?.GetValue<int>() is int seq) since = Math.Max(since, seq);
        if (status is "COMPLETED" or "IN_PROGRESS" or "FAILED" or "CANCELED" or "TIMED_OUT")
        {
            Console.WriteLine($"intent {intentId} → {status}");
            if (status is "COMPLETED" or "IN_PROGRESS") Console.WriteLine("SUCCESS");
            return;
        }
    }
    await Task.Delay(1000);
}
Console.Error.WriteLine("timeout");
