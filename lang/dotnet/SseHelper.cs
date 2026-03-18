using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace AxmeExamples;

/// <summary>
/// Shared SSE helper for agent intent stream polling.
/// The .NET SDK does not include a built-in SSE/listen method.
/// </summary>
public static class SseHelper
{
    private static readonly HttpClient Http = new();

    public static async Task<List<JsonObject>> PollAgentStreamAsync(
        string baseUrl, string apiKey, string agentAddress,
        int since = 0, int waitSeconds = 15, CancellationToken ct = default)
    {
        var path = agentAddress.StartsWith("agent://") ? agentAddress["agent://".Length..] : agentAddress;
        var url = $"{baseUrl}/v1/agents/{path}/intents/stream?since={since}&wait_seconds={waitSeconds}";

        using var req = new HttpRequestMessage(HttpMethod.Get, url);
        req.Headers.Add("x-api-key", apiKey);
        req.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("text/event-stream"));

        using var resp = await Http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ct);
        resp.EnsureSuccessStatusCode();

        var results = new List<JsonObject>();
        using var reader = new StreamReader(await resp.Content.ReadAsStreamAsync(ct));

        var eventType = "";
        var data = "";

        while (await reader.ReadLineAsync(ct) is { } line)
        {
            if (line.StartsWith("event: ")) eventType = line[7..].Trim();
            else if (line.StartsWith("data: ")) data += line[6..];
            else if (line.Length == 0 && data.Length > 0)
            {
                if (eventType.StartsWith("intent."))
                {
                    var obj = JsonNode.Parse(data)?.AsObject();
                    if (obj != null) results.Add(obj);
                }
                eventType = "";
                data = "";
            }
        }
        return results;
    }

    public static string Env(string key, string def = "") =>
        Environment.GetEnvironmentVariable(key) is { Length: > 0 } v ? v : def;

    public static string Str(JsonObject obj, string key, string def = "") =>
        obj.TryGetPropertyValue(key, out var v) && v is JsonValue jv ? jv.ToString() : def;

    public static JsonObject EffectivePayload(JsonObject intent)
    {
        var raw = intent["payload"]?.AsObject() ?? new JsonObject();
        return raw["parent_payload"]?.AsObject() ?? raw;
    }

    public static JsonObject UnwrapIntent(JsonObject resp) =>
        resp["intent"]?.AsObject() ?? resp;

    public static bool IsActionable(JsonObject intent)
    {
        var status = (Str(intent, "lifecycle_status") is { Length: > 0 } s ? s : Str(intent, "status")).ToUpper();
        return status is "CREATED" or "DELIVERED" or "ACKNOWLEDGED" or "IN_PROGRESS" or "WAITING";
    }
}
