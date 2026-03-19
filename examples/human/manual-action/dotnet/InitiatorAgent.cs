using System.Text.Json.Nodes;
using Axme.Sdk;
using AxmeExamples;

namespace AxmeExamples.Human.ManualAction;

/// <summary>
/// Manual action — human/manual-action example (.NET).
///
/// Creates an intent with a human manual-action step. The workflow pauses
/// and emails the technician a link to report on a physical rack inspection.
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
        var notifyEmail = SseHelper.Env("AXME_NOTIFY_EMAIL", "dc-ops@example.com");
        if (string.IsNullOrEmpty(apiKey)) { Console.Error.WriteLine("AXME_API_KEY is required"); return; }

        var client = new AxmeClient(new AxmeClientConfig { ApiKey = apiKey, BaseUrl = baseUrl });
        Console.WriteLine("creating manual-action intent ...");

        var created = await client.CreateIntentAsync(new JsonObject
        {
            ["intent_type"] = "intent.dc.manual_action.v1",
            ["from_agent"] = "initiator://human-manual-action",
            ["to_agent"] = "agent://agent_core",
            ["correlation_id"] = Guid.NewGuid().ToString(),
            ["payload"] = new JsonObject { ["rack_id"] = "B-14", ["location"] = "DC-East",
                ["alert"] = "elevated_temperature" },
            ["human_task"] = new JsonObject
            {
                ["title"] = "Inspect server rack B-14",
                ["description"] = "Elevated temperature alert in rack B-14 at DC-East. Please physically inspect the rack, check airflow and cooling, and report findings with evidence.",
                ["task_type"] = "manual_action",
                ["notify_email"] = notifyEmail,
                ["allowed_outcomes"] = new JsonArray("completed", "failed"),
                ["evidence_required"] = true
            }
        });

        var intentId = created["intent_id"]?.ToString() ?? "";
        Console.WriteLine($"intent created: {intentId}");
        Console.WriteLine("Check your email for the task link.");
    }
}
