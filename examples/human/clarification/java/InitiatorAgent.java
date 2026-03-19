package ai.axme.examples.human.clarification;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/**
 * Clarification — human/clarification example (Java).
 *
 * Creates an intent with a human clarification step. The workflow pauses
 * and emails the assignee a link to provide missing information or decline.
 *
 * Run:
 *   AXME_API_KEY=<key> java InitiatorAgent.java
 */
public class InitiatorAgent {
    public static void main(String[] args) throws Exception {
        String apiKey = System.getenv("AXME_API_KEY");
        String baseUrl = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        String notifyEmail = SseHelper.env("AXME_NOTIFY_EMAIL", "cs@example.com");
        if (apiKey == null || apiKey.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }

        AxmeClient client = new AxmeClient(new AxmeClientConfig(baseUrl, apiKey));
        System.out.println("creating clarification intent ...");

        Map<String, Object> created = client.createIntent(Map.of(
                "intent_type", "intent.customer.clarification.v1",
                "from_agent", "initiator://human-clarification",
                "to_agent", "agent://agent_core",
                "correlation_id", UUID.randomUUID().toString(),
                "payload", Map.of("customer", "ABC Corp", "ticket", "ONBOARD-429"),
                "human_task", Map.of(
                        "title", "Clarification needed \u2014 ABC Corp onboarding",
                        "description", "Ticket ONBOARD-429 for ABC Corp requires additional information before onboarding can proceed. Please provide the requested details or decline.",
                        "task_type", "clarification",
                        "notify_email", notifyEmail,
                        "allowed_outcomes", List.of("provided", "declined"),
                        "required_comment", true)
        ), RequestOptions.none());

        String intentId = (String) created.get("intent_id");
        System.out.printf("intent created: %s%n", intentId);
        System.out.println("Check your email for the task link.");
    }
}
