using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Delivery;

public class InboxAgent
{
    public static async Task Main(string[] args)
    {
        var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        var apiKey = SseHelper.Env("AXME_API_KEY");
        var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "fulfillment-service-agent");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine($"fulfillment-service-agent starting  address={addr}");

        var shipping = new Dictionary<string, string> { ["express"] = "1-2 business days", ["standard"] = "3-5 business days", ["economy"] = "7-10 business days" };
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
                    var intent = await client.GetIntentAsync(id);
                    var p = intent["payload"]?.AsObject() ?? new JsonObject();
                    var orderId = SseHelper.Str(p, "order_id");
                    var ship = SseHelper.Str(p, "shipping", "standard");
                    var items = p["items"]?.AsArray();
                    var total = items?.Sum(i => i?["quantity"]?.GetValue<int>() ?? 0) ?? 0;

                    JsonObject res;
                    if (string.IsNullOrEmpty(orderId)) res = new JsonObject { ["action"] = "fail", ["reason"] = "order_id required" };
                    else if (items == null || items.Count == 0) res = new JsonObject { ["action"] = "fail", ["reason"] = "items empty" };
                    else if (!shipping.ContainsKey(ship)) res = new JsonObject { ["action"] = "fail", ["reason"] = "unknown shipping" };
                    else res = new JsonObject { ["action"] = "complete", ["fulfillment_id"] = $"FUL-{Math.Abs((orderId + SseHelper.Str(p, "customer_id")).GetHashCode()) % 100000:D5}",
                        ["tracking_number"] = $"AXME-{orderId.ToUpper()}-{Math.Abs(orderId.GetHashCode()) % 10000:D4}",
                        ["warehouse"] = "WH-US-EAST-1", ["shipping_method"] = ship, ["eta"] = shipping[ship], ["items_shipped"] = total, ["status"] = "fulfilled" };

                    await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
                    Console.WriteLine($"resumed {id} action={res["action"]}");
                }
            }
            catch { await Task.Delay(2000); }
        }
    }
}
