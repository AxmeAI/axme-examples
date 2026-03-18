using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
var apiKey = SseHelper.Env("AXME_API_KEY");
var toAgent = SseHelper.Env("AXME_TO_AGENT");
if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }
if (string.IsNullOrEmpty(toAgent)) { Console.Error.WriteLine("AXME_TO_AGENT is required"); return; }

var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
Console.WriteLine($"firing intent to {toAgent} ...");

var created = await client.CreateIntentAsync(new JsonObject
{
    ["intent_type"] = "intent.compliance.check.v1",
    ["from_agent"] = "initiator://fire-and-forget", ["to_agent"] = toAgent,
    ["reply_to"] = "initiator://fire-and-forget",
    ["correlation_id"] = Guid.NewGuid().ToString(),
    ["payload"] = new JsonObject { ["change_id"] = "CHG-FIRE-FORGET-001", ["service"] = "payments-service",
        ["version"] = "2.1.0", ["environment"] = "staging", ["change_type"] = "config_update", ["risk_level"] = "medium" }
});
var intentId = created["intent_id"]?.ToString() ?? "";
Console.WriteLine($"intent sent: {intentId} — disconnecting");
Console.WriteLine("doing other work for 15 seconds...");
await Task.Delay(15000);

Console.WriteLine("checking intent status...");
var resp = await client.GetIntentAsync(intentId);
var intent = SseHelper.UnwrapIntent(resp);
var status = SseHelper.Str(intent, "lifecycle_status") is { Length: > 0 } s ? s : SseHelper.Str(intent, "status");
Console.WriteLine($"intent {intentId} → {status}");
if (status is "COMPLETED" or "IN_PROGRESS") Console.WriteLine("SUCCESS — fire-and-forget verified");
