package ai.axme.examples.human.confirmation;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/**
 * Confirmation — human/confirmation example (Java).
 *
 * Creates an intent with a human confirmation step. The workflow pauses
 * and emails the assignee a link to confirm or deny DNS propagation.
 *
 * Run:
 *   AXME_API_KEY=<key> java InitiatorAgent.java
 */
public class InitiatorAgent {
    public static void main(String[] args) throws Exception {
        String apiKey = System.getenv("AXME_API_KEY");
        String baseUrl = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        String notifyEmail = SseHelper.env("AXME_NOTIFY_EMAIL", "ops@example.com");
        if (apiKey == null || apiKey.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }

        AxmeClient client = new AxmeClient(new AxmeClientConfig(baseUrl, apiKey));
        System.out.println("creating confirmation intent ...");

        Map<String, Object> created = client.createIntent(Map.of(
                "intent_type", "intent.dns.confirmation.v1",
                "from_agent", "initiator://human-confirmation",
                "to_agent", "agent://agent_core",
                "correlation_id", UUID.randomUUID().toString(),
                "payload", Map.of("domain", "api.example.com", "record_type", "CNAME",
                        "new_value", "new-lb.example.com"),
                "human_task", Map.of(
                        "title", "Confirm DNS propagation",
                        "description", "DNS change submitted: api.example.com CNAME -> new-lb.example.com. Please verify propagation is complete.",
                        "task_type", "confirmation",
                        "notify_email", notifyEmail,
                        "allowed_outcomes", List.of("confirmed", "denied"))
        ), RequestOptions.none());

        String intentId = (String) created.get("intent_id");
        System.out.printf("intent created: %s%n", intentId);
        System.out.println("Check your email for the task link.");
    }
}
