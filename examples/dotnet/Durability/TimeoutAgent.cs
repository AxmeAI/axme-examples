using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Durability;

public class TimeoutAgent
{
    public static async Task Main(string[] args)
    {
        var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        var apiKey = SseHelper.Env("AXME_API_KEY");
        var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "slow-batch-processor");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine($"slow-batch-processor starting  address={addr}");
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

                    var batchId = SseHelper.Str(p, "batch_id", "?");
                    var rc = (int)(p["record_count"]?.GetValue<double>() ?? 0);
                    JsonObject res;
                    if (rc > 10000) res = new JsonObject { ["action"] = "fail", ["batch_id"] = batchId, ["error"] = $"batch too large: {rc}" };
                    else res = new JsonObject { ["action"] = "complete", ["batch_id"] = batchId, ["record_count"] = rc, ["processed"] = true };
                    await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
                    Console.WriteLine($"resumed {id} action={res["action"]}");
                }
            }
            catch { await Task.Delay(2000); }
        }
    }
}
