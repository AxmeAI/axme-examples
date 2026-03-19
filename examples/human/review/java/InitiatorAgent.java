package ai.axme.examples.human.review;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/**
 * Review — human/review example (Java).
 *
 * Creates an intent with a human review step. The workflow pauses
 * and emails the reviewer a link to approve, request changes, or reject a PR.
 *
 * Run:
 *   AXME_API_KEY=<key> java InitiatorAgent.java
 */
public class InitiatorAgent {
    public static void main(String[] args) throws Exception {
        String apiKey = System.getenv("AXME_API_KEY");
        String baseUrl = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        String notifyEmail = SseHelper.env("AXME_NOTIFY_EMAIL", "reviewer@example.com");
        if (apiKey == null || apiKey.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }

        AxmeClient client = new AxmeClient(new AxmeClientConfig(baseUrl, apiKey));
        System.out.println("creating review intent ...");

        Map<String, Object> created = client.createIntent(Map.of(
                "intent_type", "intent.code.review.v1",
                "from_agent", "initiator://human-review",
                "to_agent", "agent://agent_core",
                "correlation_id", UUID.randomUUID().toString(),
                "payload", Map.of("pr_number", 847, "title", "Add retry logic to payment service",
                        "author", "alice"),
                "human_task", Map.of(
                        "title", "Review PR #847",
                        "description", "PR #847 'Add retry logic to payment service' by alice is ready for review. Please approve, request changes, or reject.",
                        "task_type", "review",
                        "notify_email", notifyEmail,
                        "allowed_outcomes", List.of("approved", "changes_requested", "rejected"))
        ), RequestOptions.none());

        String intentId = (String) created.get("intent_id");
        System.out.printf("intent created: %s%n", intentId);
        System.out.println("Check your email for the task link.");
    }
}
