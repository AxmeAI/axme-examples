using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Human.Review;

/// <summary>
/// Review — human/review example (.NET).
///
/// Creates an intent with a human review step. The workflow pauses
/// and emails the reviewer a link to approve, request changes, or reject a PR.
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
        var notifyEmail = SseHelper.Env("AXME_NOTIFY_EMAIL", "reviewer@example.com");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine("creating review intent ...");

        var created = await client.CreateIntentAsync(new JsonObject
        {
            ["intent_type"] = "intent.code.review.v1",
            ["from_agent"] = "initiator://human-review",
            ["to_agent"] = "agent://agent_core",
            ["correlation_id"] = Guid.NewGuid().ToString(),
            ["payload"] = new JsonObject { ["pr_number"] = 847, ["title"] = "Add retry logic to payment service",
                ["author"] = "alice" },
            ["human_task"] = new JsonObject
            {
                ["title"] = "Review PR #847",
                ["description"] = "PR #847 'Add retry logic to payment service' by alice is ready for review. Please approve, request changes, or reject.",
                ["task_type"] = "review",
                ["notify_email"] = notifyEmail,
                ["allowed_outcomes"] = new JsonArray("approved", "changes_requested", "rejected")
            }
        });

        var intentId = created["intent_id"]?.ToString() ?? "";
        Console.WriteLine($"intent created: {intentId}");
        Console.WriteLine("Check your email for the task link.");
    }
}
