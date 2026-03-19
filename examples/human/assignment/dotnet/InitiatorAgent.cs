using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Human.Assignment;

/// <summary>
/// Assignment — human/assignment example (.NET).
///
/// Creates an intent with a human assignment step. The workflow pauses
/// and emails the on-call manager a link to assign an incident commander.
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
        var notifyEmail = SseHelper.Env("AXME_NOTIFY_EMAIL", "oncall@example.com");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine("creating assignment intent ...");

        var created = await client.CreateIntentAsync(new JsonObject
        {
            ["intent_type"] = "intent.incident.assignment.v1",
            ["from_agent"] = "initiator://human-assignment",
            ["to_agent"] = "agent://agent_core",
            ["correlation_id"] = Guid.NewGuid().ToString(),
            ["payload"] = new JsonObject { ["incident_id"] = "INC-2026-1847", ["severity"] = "P1",
                ["service"] = "payment-api" },
            ["human_task"] = new JsonObject
            {
                ["title"] = "Assign incident commander",
                ["description"] = "Incident INC-2026-1847 classified as P1 affecting payment-api. Please designate an incident commander.",
                ["task_type"] = "assignment",
                ["notify_email"] = notifyEmail,
                ["allowed_outcomes"] = new JsonArray("assigned", "declined"),
                ["form_schema"] = new JsonObject
                {
                    ["type"] = "object",
                    ["required"] = new JsonArray("assignee"),
                    ["properties"] = new JsonObject
                    {
                        ["assignee"] = new JsonObject { ["type"] = "string", ["description"] = "Email of the designated incident commander" },
                        ["priority"] = new JsonObject { ["type"] = "string", ["description"] = "Override priority level",
                            ["enum"] = new JsonArray("P1", "P2", "P3", "P4") }
                    }
                }
            }
        });

        var intentId = created["intent_id"]?.ToString() ?? "";
        Console.WriteLine($"intent created: {intentId}");
        Console.WriteLine("Check your email for the task link.");
    }
}
