package ai.axme.examples.human.assignment;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/**
 * Assignment — human/assignment example (Java).
 *
 * Creates an intent with a human assignment step. The workflow pauses
 * and emails the on-call manager a link to assign an incident commander.
 *
 * Run:
 *   AXME_API_KEY=<key> java InitiatorAgent.java
 */
public class InitiatorAgent {
    public static void main(String[] args) throws Exception {
        String apiKey = System.getenv("AXME_API_KEY");
        String baseUrl = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        String notifyEmail = SseHelper.env("AXME_NOTIFY_EMAIL", "oncall@example.com");
        if (apiKey == null || apiKey.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }

        AxmeClient client = new AxmeClient(new AxmeClientConfig(baseUrl, apiKey));
        System.out.println("creating assignment intent ...");

        Map<String, Object> created = client.createIntent(Map.of(
                "intent_type", "intent.incident.assignment.v1",
                "from_agent", "initiator://human-assignment",
                "to_agent", "agent://agent_core",
                "correlation_id", UUID.randomUUID().toString(),
                "payload", Map.of("incident_id", "INC-2026-1847", "severity", "P1",
                        "service", "payment-api"),
                "human_task", Map.ofEntries(
                        Map.entry("title", "Assign incident commander"),
                        Map.entry("description", "Incident INC-2026-1847 classified as P1 affecting payment-api. Please designate an incident commander."),
                        Map.entry("task_type", "assignment"),
                        Map.entry("notify_email", notifyEmail),
                        Map.entry("allowed_outcomes", List.of("assigned", "declined")),
                        Map.entry("form_schema", Map.of(
                                "type", "object",
                                "required", List.of("assignee"),
                                "properties", Map.of(
                                        "assignee", Map.of("type", "string", "description", "Email of the designated incident commander"),
                                        "priority", Map.of("type", "string", "description", "Override priority level", "enum", List.of("P1", "P2", "P3", "P4"))))))
        ), RequestOptions.none());

        String intentId = (String) created.get("intent_id");
        System.out.printf("intent created: %s%n", intentId);
        System.out.println("Check your email for the task link.");
    }
}
