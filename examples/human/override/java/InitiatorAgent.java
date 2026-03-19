package ai.axme.examples.human.override;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/**
 * Override — human/override example (Java).
 *
 * Creates an intent with a human override step. The workflow pauses
 * and emails the senior operator a link to approve or reject a deployment
 * freeze override with justification.
 *
 * Run:
 *   AXME_API_KEY=<key> java InitiatorAgent.java
 */
public class InitiatorAgent {
    public static void main(String[] args) throws Exception {
        String apiKey = System.getenv("AXME_API_KEY");
        String baseUrl = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        String notifyEmail = SseHelper.env("AXME_NOTIFY_EMAIL", "senior-ops@example.com");
        if (apiKey == null || apiKey.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }

        AxmeClient client = new AxmeClient(new AxmeClientConfig(baseUrl, apiKey));
        System.out.println("creating override intent ...");

        Map<String, Object> created = client.createIntent(Map.of(
                "intent_type", "intent.deploy.override.v1",
                "from_agent", "initiator://human-override",
                "to_agent", "agent://agent_core",
                "correlation_id", UUID.randomUUID().toString(),
                "payload", Map.of("service", "api-gateway", "version", "v3.5.0",
                        "ticket", "CHG-2026-892"),
                "human_task", Map.of(
                        "title", "Override deployment freeze",
                        "description", "Deployment of api-gateway v3.5.0 is blocked by a deployment freeze (ticket CHG-2026-892). A senior operator must approve the override with justification or reject.",
                        "task_type", "override",
                        "notify_email", notifyEmail,
                        "allowed_outcomes", List.of("override_approved", "rejected"),
                        "required_comment", true)
        ), RequestOptions.none());

        String intentId = (String) created.get("intent_id");
        System.out.printf("intent created: %s%n", intentId);
        System.out.println("Check your email for the task link.");
    }
}
