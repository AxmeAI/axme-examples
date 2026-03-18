using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Internal;

public class DelayAgent
{
    public static async Task Main(string[] args)
    {
        var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        var apiKey = SseHelper.Env("AXME_API_KEY");
        var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "change-window-validator");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine($"change-window-validator starting  address={addr}");
        string[] windows = ["MW-2026-Q1-01","MW-2026-Q1-02","MW-2026-Q1-03","MW-2026-Q1-04","MW-2026-Q1-05","MW-2026-Q1-06"];
        string[] types = ["config_update","dependency_update","rollback","hotfix"];
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

                    var cid = SseHelper.Str(p, "change_id", "?"); var env = SseHelper.Str(p, "environment");
                    var ct = SseHelper.Str(p, "change_type"); var wid = SseHelper.Str(p, "window_id");
                    bool ok = true; string reason = $"{cid}: validated";

                    if (!types.Contains(ct)) { ok = false; reason = $"{cid}: change_type not allowed"; }
                    else if (env == "production" && string.IsNullOrEmpty(wid)) { ok = false; reason = $"{cid}: production requires window_id"; }
                    else if (env == "production" && !windows.Contains(wid)) { ok = false; reason = $"{cid}: window_id not approved"; }

                    var res = new JsonObject { ["action"] = ok ? "complete" : "fail", ["allowed"] = ok, ["reason"] = reason };
                    if (ok && !string.IsNullOrEmpty(wid) && windows.Contains(wid)) { res["window_id"] = wid; res["window_approved"] = true; }
                    await client.ResumeIntentAsync(id, res, new RequestOptions { OwnerAgent = addr });
                    Console.WriteLine($"resumed {id} (allowed={ok})");
                }
            }
            catch { await Task.Delay(2000); }
        }
    }
}
