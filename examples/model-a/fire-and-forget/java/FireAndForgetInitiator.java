package ai.axme.examples.modela;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Model A — Fire and Forget (Java). */
public class FireAndForgetInitiator {
    public static void main(String[] args) throws Exception {
        String apiKey = System.getenv("AXME_API_KEY");
        String baseUrl = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        String toAgent = System.getenv("AXME_TO_AGENT");
        if (apiKey == null || apiKey.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        if (toAgent == null || toAgent.isEmpty()) { System.err.println("AXME_TO_AGENT is required"); System.exit(1); }

        AxmeClient client = new AxmeClient(new AxmeClientConfig(baseUrl, apiKey));
        System.out.printf("firing intent to %s ...%n", toAgent);

        Map<String, Object> created = client.createIntent(Map.of(
                "intent_type", "intent.compliance.check.v1",
                "from_agent", "initiator://fire-and-forget", "to_agent", toAgent,
                "reply_to", "initiator://fire-and-forget",
                "correlation_id", UUID.randomUUID().toString(),
                "payload", Map.of("change_id", "CHG-FIRE-FORGET-001", "service", "payments-service",
                        "version", "2.1.0", "environment", "staging", "change_type", "config_update", "risk_level", "medium")
        ), RequestOptions.none());
        String intentId = (String) created.get("intent_id");
        System.out.printf("intent sent: %s — disconnecting%n", intentId);

        System.out.println("doing other work for 15 seconds...");
        Thread.sleep(15000);

        System.out.println("checking intent status...");
        Map<String, Object> resp = client.getIntent(intentId, RequestOptions.none());
        Map<String, Object> intent = SseHelper.unwrapIntent(resp);
        String status = SseHelper.str(intent, "lifecycle_status");
        if (status.isEmpty()) status = SseHelper.str(intent, "status");
        System.out.printf("intent %s → %s%n", intentId, status);
        if ("COMPLETED".equals(status) || "IN_PROGRESS".equals(status)) System.out.println("SUCCESS — fire-and-forget verified");
    }
}
