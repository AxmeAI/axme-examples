using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Human.Clarification;

/// <summary>
/// Clarification — human/clarification example (.NET).
///
/// Creates an intent with a human clarification step. The workflow pauses
/// and emails the assignee a link to provide missing information or decline.
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
        var notifyEmail = SseHelper.Env("AXME_NOTIFY_EMAIL", "cs@example.com");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine("creating clarification intent ...");

        var created = await client.CreateIntentAsync(new JsonObject
        {
            ["intent_type"] = "intent.customer.clarification.v1",
            ["from_agent"] = "initiator://human-clarification",
            ["to_agent"] = "agent://agent_core",
            ["correlation_id"] = Guid.NewGuid().ToString(),
            ["payload"] = new JsonObject { ["customer"] = "ABC Corp", ["ticket"] = "ONBOARD-429" },
            ["human_task"] = new JsonObject
            {
                ["title"] = "Clarification needed \u2014 ABC Corp onboarding",
                ["description"] = "Ticket ONBOARD-429 for ABC Corp requires additional information before onboarding can proceed. Please provide the requested details or decline.",
                ["task_type"] = "clarification",
                ["notify_email"] = notifyEmail,
                ["allowed_outcomes"] = new JsonArray("provided", "declined"),
                ["required_comment"] = true
            }
        });

        var intentId = created["intent_id"]?.ToString() ?? "";
        Console.WriteLine($"intent created: {intentId}");
        Console.WriteLine("Check your email for the task link.");
    }
}
