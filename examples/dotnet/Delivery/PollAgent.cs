using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Delivery;

public class PollAgent
{
    public static async Task Main(string[] args)
    {
        var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        var apiKey = SseHelper.Env("AXME_API_KEY");
        var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "batch-processor-agent");
        var interval = int.Parse(SseHelper.Env("POLL_INTERVAL", "10")) * 1000;
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine($"batch-processor-agent starting  address={addr}  binding=poll");

        var counts = new Dictionary<string, int> { ["transactions"] = 14203, ["invoices"] = 1847, ["orders"] = 3291, ["events"] = 82014 };
        var seen = new HashSet<string>();

        while (true)
        {
            try
            {
                foreach (var d in await SseHelper.PollAgentStreamAsync(baseUrl, apiKey, addr, 0, 2))
                {
                    var id = SseHelper.Str(d, "intent_id");
                    if (string.IsNullOrEmpty(id) || !seen.Add(id)) continue;
                    var intent = await client.GetIntentAsync(id);
                    var p = intent["payload"]?.AsObject() ?? new JsonObject();
                    var batchId = SseHelper.Str(p, "batch_id", "?");
                    var rt = SseHelper.Str(p, "record_type");
                    var dr = SseHelper.Str(p, "date_range");

                    JsonObject res;
                    if (batchId == "?") res = new JsonObject { ["action"] = "fail", ["reason"] = "batch_id is required" };
                    else if (!counts.ContainsKey(rt)) res = new JsonObject { ["action"] = "fail", ["reason"] = "unsupported record_type" };
                    else if (string.IsNullOrEmpty(dr)) res = new JsonObject { ["action"] = "fail", ["reason"] = "date_range is required" };
                    else res = new JsonObject { ["action"] = "complete", ["batch_id"] = batchId, ["record_type"] = rt, ["date_range"] = dr, ["record_count"] = counts[rt], ["status"] = "processed" };

                    await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
                    Console.WriteLine($"resumed {id} action={res["action"]}");
                }
            }
            catch { /* timeout normal */ }
            await Task.Delay(interval);
        }
    }
}
