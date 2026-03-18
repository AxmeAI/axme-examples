using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
var apiKey = SseHelper.Env("AXME_API_KEY");
var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "webhook-receiver-agent");
if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
Console.WriteLine($"webhook-receiver starting  address={addr}");
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

            var et = SseHelper.Str(p, "event_type", "unknown"); var src = SseHelper.Str(p, "source");
            var tid = SseHelper.Str(p, "test_id");
            var fp = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes($"{et}:{src}:{tid}"))).ToLower()[..16];

            var res = new JsonObject { ["action"] = "complete", ["event_type"] = et, ["source"] = src,
                ["fingerprint"] = fp, ["processed"] = true, ["note"] = $"webhook '{et}' processed" };
            await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
            Console.WriteLine($"resumed {id} fingerprint={fp}");
        }
    }
    catch { await Task.Delay(2000); }
}
