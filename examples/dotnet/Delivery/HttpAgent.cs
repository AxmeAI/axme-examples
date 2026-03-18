using System.Net;
using System.Text.Json;
using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Delivery;

public class HttpAgent
{
    public static async Task Main(string[] args)
    {
        var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        var apiKey = SseHelper.Env("AXME_API_KEY");
        var addr = SseHelper.Env("AXME_AGENT_ADDRESS", "http-order-processor");
        var port = int.Parse(SseHelper.Env("PORT", "8080"));
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        string[] currencies = ["USD", "EUR", "GBP", "JPY"];

        var listener = new HttpListener();
        listener.Prefixes.Add($"http://+:{port}/");
        listener.Start();
        Console.WriteLine($"http-order-processor starting  port={port}");

        while (true)
        {
            var ctx = await listener.GetContextAsync();
            if (ctx.Request.Url?.AbsolutePath == "/health")
            {
                ctx.Response.StatusCode = 200;
                await ctx.Response.OutputStream.WriteAsync(System.Text.Encoding.UTF8.GetBytes("{\"status\":\"ok\"}"));
                ctx.Response.Close(); continue;
            }
            if (ctx.Request.HttpMethod != "POST" || ctx.Request.Url?.AbsolutePath != "/intent")
            {
                ctx.Response.StatusCode = 404; ctx.Response.Close(); continue;
            }
            using var reader = new StreamReader(ctx.Request.InputStream);
            var body = await reader.ReadToEndAsync();
            ctx.Response.StatusCode = 200;
            await ctx.Response.OutputStream.WriteAsync(System.Text.Encoding.UTF8.GetBytes("{\"ack\":true}"));
            ctx.Response.Close();

            var envelope = JsonNode.Parse(body)?.AsObject();
            var intentId = SseHelper.Str(envelope ?? new JsonObject(), "intent_id");
            if (!string.IsNullOrEmpty(intentId))
            {
                _ = Task.Run(async () =>
                {
                    try
                    {
                        var intent = await client.GetIntentAsync(intentId);
                        var p = intent["payload"]?.AsObject() ?? new JsonObject();
                        var orderId = SseHelper.Str(p, "order_id");
                        var currency = SseHelper.Str(p, "currency");
                        JsonObject res;
                        if (SseHelper.Str(p, "event_type") != "order.placed") res = new JsonObject { ["action"] = "fail", ["reason"] = "unexpected event_type" };
                        else if (string.IsNullOrEmpty(orderId)) res = new JsonObject { ["action"] = "fail", ["reason"] = "order_id required" };
                        else if (!currencies.Contains(currency)) res = new JsonObject { ["action"] = "fail", ["reason"] = "unsupported currency" };
                        else res = new JsonObject { ["action"] = "complete", ["order_id"] = orderId, ["tracking_id"] = $"TRK-{orderId.ToUpper()}-{Math.Abs(orderId.GetHashCode()) % 100000:D5}", ["status"] = "accepted" };
                        await client.ResumeIntentAsync(intentId, res, new RequestOptions { OwnerAgent = addr });
                        Console.WriteLine($"resumed {intentId}");
                    }
                    catch (Exception ex) { Console.Error.WriteLine($"error: {ex.Message}"); }
                });
            }
        }
    }
}
