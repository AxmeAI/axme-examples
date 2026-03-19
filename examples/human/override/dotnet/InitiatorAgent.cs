using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Human.Override;

/// <summary>
/// Override — human/override example (.NET).
///
/// Creates an intent with a human override step. The workflow pauses
/// and emails the senior operator a link to approve or reject a deployment
/// freeze override with justification.
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
        var notifyEmail = SseHelper.Env("AXME_NOTIFY_EMAIL", "senior-ops@example.com");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine("creating override intent ...");

        var created = await client.CreateIntentAsync(new JsonObject
        {
            ["intent_type"] = "intent.deploy.override.v1",
            ["from_agent"] = "initiator://human-override",
            ["to_agent"] = "agent://agent_core",
            ["correlation_id"] = Guid.NewGuid().ToString(),
            ["payload"] = new JsonObject { ["service"] = "api-gateway", ["version"] = "v3.5.0",
                ["ticket"] = "CHG-2026-892" },
            ["human_task"] = new JsonObject
            {
                ["title"] = "Override deployment freeze",
                ["description"] = "Deployment of api-gateway v3.5.0 is blocked by a deployment freeze (ticket CHG-2026-892). A senior operator must approve the override with justification or reject.",
                ["task_type"] = "override",
                ["notify_email"] = notifyEmail,
                ["allowed_outcomes"] = new JsonArray("override_approved", "rejected"),
                ["required_comment"] = true
            }
        });

        var intentId = created["intent_id"]?.ToString() ?? "";
        Console.WriteLine($"intent created: {intentId}");
        Console.WriteLine("Check your email for the task link.");
    }
}
