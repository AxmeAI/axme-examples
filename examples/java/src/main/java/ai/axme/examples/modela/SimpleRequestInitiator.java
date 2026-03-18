package ai.axme.examples.modela;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Model A — Simple Request: initiator waits for agent response (Java). */
public class SimpleRequestInitiator {
    public static void main(String[] args) throws Exception {
        String apiKey = System.getenv("AXME_API_KEY");
        String baseUrl = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        String toAgent = System.getenv("AXME_TO_AGENT");
        if (apiKey == null || apiKey.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        if (toAgent == null || toAgent.isEmpty()) { System.err.println("AXME_TO_AGENT is required"); System.exit(1); }

        AxmeClient client = new AxmeClient(new AxmeClientConfig(baseUrl, apiKey));
        System.out.printf("creating intent to %s ...%n", toAgent);

        Map<String, Object> created = client.createIntent(Map.of(
                "intent_type", "intent.compliance.check.v1",
                "from_agent", "initiator://simple-request",
                "to_agent", toAgent,
                "correlation_id", UUID.randomUUID().toString(),
                "payload", Map.of("change_id", "CHG-MODEL-A-001", "service", "api-gateway", "version", "4.0.0",
                        "environment", "staging", "change_type", "config_update", "risk_level", "low")
        ), RequestOptions.none());
        String intentId = (String) created.get("intent_id");
        System.out.printf("intent created: %s%nwaiting for agent response...%n", intentId);

        int since = 0;
        long deadline = System.currentTimeMillis() + 120_000;
        while (System.currentTimeMillis() < deadline) {
            Map<String, Object> events = client.listIntentEvents(intentId, since, RequestOptions.none());
            @SuppressWarnings("unchecked") List<Map<String, Object>> evts = (List<Map<String, Object>>) events.getOrDefault("events", List.of());
            for (Map<String, Object> evt : evts) {
                String status = SseHelper.str(evt, "status");
                if (evt.get("seq") instanceof Number n) since = Math.max(since, n.intValue());
                if (Set.of("COMPLETED", "IN_PROGRESS", "FAILED", "CANCELED", "TIMED_OUT").contains(status)) {
                    System.out.printf("intent %s → %s%n", intentId, status);
                    if ("COMPLETED".equals(status) || "IN_PROGRESS".equals(status)) System.out.println("SUCCESS");
                    return;
                }
            }
            Thread.sleep(1000);
        }
        System.err.println("timeout");
    }
}
