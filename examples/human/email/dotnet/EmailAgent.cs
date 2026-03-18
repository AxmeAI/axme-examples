using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Human;

public class EmailAgent
{
    public static async Task Main(string[] args)
    {
        var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        var apiKey = SseHelper.Env("AXME_API_KEY");
        var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "budget-envelope-validator");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine($"budget-envelope-validator starting  address={addr}");
        var envelopes = new Dictionary<string, double> { ["cloud_infrastructure"] = 50000, ["software_licenses"] = 20000, ["contractor_services"] = 40000, ["hardware"] = 15000 };
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

                    var amount = p["amount"]?.GetValue<double>() ?? 0;
                    var category = SseHelper.Str(p, "category");
                    var currency = SseHelper.Str(p, "currency", "USD");

                    JsonObject res;
                    if (!envelopes.TryGetValue(category, out var envelope))
                        res = new JsonObject { ["action"] = "fail", ["within_envelope"] = false, ["reason"] = "unknown category" };
                    else if (amount > envelope)
                        res = new JsonObject { ["action"] = "fail", ["within_envelope"] = false, ["reason"] = "exceeds envelope" };
                    else
                    {
                        var headroom = Math.Round((envelope - amount) / envelope * 1000) / 10;
                        res = new JsonObject { ["action"] = "complete", ["within_envelope"] = true,
                            ["reason"] = $"{currency} {amount:N0} within {category} ({headroom}% headroom)",
                            ["envelope"] = envelope, ["headroom_pct"] = headroom };
                    }
                    await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
                    Console.WriteLine($"resumed {id} (within_envelope={res["within_envelope"]})");
                }
            }
            catch { await Task.Delay(2000); }
        }
    }
}
