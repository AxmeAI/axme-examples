package ai.axme.examples.human.manualaction;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/**
 * Manual action — human/manual-action example (Java).
 *
 * Creates an intent with a human manual-action step. The workflow pauses
 * and emails the technician a link to report on a physical rack inspection.
 *
 * Run:
 *   AXME_API_KEY=<key> java InitiatorAgent.java
 */
public class InitiatorAgent {
    public static void main(String[] args) throws Exception {
        String apiKey = System.getenv("AXME_API_KEY");
        String baseUrl = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        String notifyEmail = SseHelper.env("AXME_NOTIFY_EMAIL", "dc-ops@example.com");
        if (apiKey == null || apiKey.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }

        AxmeClient client = new AxmeClient(new AxmeClientConfig(baseUrl, apiKey));
        System.out.println("creating manual-action intent ...");

        Map<String, Object> created = client.createIntent(Map.of(
                "intent_type", "intent.dc.manual_action.v1",
                "from_agent", "initiator://human-manual-action",
                "to_agent", "agent://agent_core",
                "correlation_id", UUID.randomUUID().toString(),
                "payload", Map.of("rack_id", "B-14", "location", "DC-East",
                        "alert", "elevated_temperature"),
                "human_task", Map.of(
                        "title", "Inspect server rack B-14",
                        "description", "Elevated temperature alert in rack B-14 at DC-East. Please physically inspect the rack, check airflow and cooling, and report findings with evidence.",
                        "task_type", "manual_action",
                        "notify_email", notifyEmail,
                        "allowed_outcomes", List.of("completed", "failed"),
                        "evidence_required", true)
        ), RequestOptions.none());

        String intentId = (String) created.get("intent_id");
        System.out.printf("intent created: %s%n", intentId);
        System.out.println("Check your email for the task link.");
    }
}
