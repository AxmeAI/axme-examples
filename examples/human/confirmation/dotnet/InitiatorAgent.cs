using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Human.Confirmation;

/// <summary>
/// Confirmation — human/confirmation example (.NET).
///
/// Creates an intent with a human confirmation step. The workflow pauses
/// and emails the assignee a link to confirm or deny DNS propagation.
///
/// Run:
///   AXME_API_KEY=&lt;key&gt; dotnet run
/// </summary>
public class InitiatorAgent
{
    public static async Task Main(string[] args)
    {
        var baseUrl = SseHelper.Env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        var apiKey = SseHelper.Env("AXME_API_KEY");
        var notifyEmail = SseHelper.Env("AXME_NOTIFY_EMAIL", "ops@example.com");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine("creating confirmation intent ...");

        var created = await client.CreateIntentAsync(new JsonObject
        {
            ["intent_type"] = "intent.dns.confirmation.v1",
            ["from_agent"] = "initiator://human-confirmation",
            ["to_agent"] = "agent://agent_core",
            ["correlation_id"] = Guid.NewGuid().ToString(),
            ["payload"] = new JsonObject { ["domain"] = "api.example.com", ["record_type"] = "CNAME",
                ["new_value"] = "new-lb.example.com" },
            ["human_task"] = new JsonObject
            {
                ["title"] = "Confirm DNS propagation",
                ["description"] = "DNS change submitted: api.example.com CNAME -> new-lb.example.com. Please verify propagation is complete.",
                ["task_type"] = "confirmation",
                ["notify_email"] = notifyEmail,
                ["allowed_outcomes"] = new JsonArray("confirmed", "denied")
            }
        });

        var intentId = created["intent_id"]?.ToString() ?? "";
        Console.WriteLine($"intent created: {intentId}");
        Console.WriteLine("Check your email for the task link.");
    }
}
