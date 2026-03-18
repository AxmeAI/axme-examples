package ai.axme.examples.modela;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Model A — Manual Multi-Step (Java). */
public class ManualMultiStepInitiator {
    public static void main(String[] args) throws Exception {
        String apiKey = System.getenv("AXME_API_KEY");
        String baseUrl = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
        String agent1 = System.getenv("AXME_AGENT_1"), agent2 = System.getenv("AXME_AGENT_2");
        if (apiKey == null || apiKey.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        if (agent1 == null || agent2 == null || agent1.isEmpty() || agent2.isEmpty()) {
            System.err.println("AXME_AGENT_1 and AXME_AGENT_2 required"); System.exit(1);
        }

        AxmeClient client = new AxmeClient(new AxmeClientConfig(baseUrl, apiKey));
        Map<String, Object> payload = Map.of("change_id", "CHG-MULTI-STEP-001", "service", "api-gateway",
                "version", "5.0.0", "environment", "staging", "change_type", "config_update",
                "risk_level", "medium", "risk_threshold", 30);

        // Step 1
        System.out.printf("STEP 1: compliance check → %s%n", agent1);
        Map<String, Object> c1 = client.createIntent(Map.of("intent_type", "intent.compliance.check.v1",
                "from_agent", "initiator://manual-multi-step", "to_agent", agent1,
                "correlation_id", UUID.randomUUID().toString(), "payload", payload), RequestOptions.none());
        String s1id = (String) c1.get("intent_id");
        String s1 = waitForDone(client, s1id, 60_000);
        System.out.printf("step 1 → %s%n", s1);
        if (!"COMPLETED".equals(s1) && !"IN_PROGRESS".equals(s1)) { System.err.println("step 1 failed — aborting"); return; }

        // Step 2
        System.out.printf("STEP 2: risk assessment → %s%n", agent2);
        Map<String, Object> p2 = new HashMap<>(payload);
        p2.put("compliance_result", "passed"); p2.put("compliance_intent_id", s1id);
        Map<String, Object> c2 = client.createIntent(Map.of("intent_type", "intent.risk.assessment.v1",
                "from_agent", "initiator://manual-multi-step", "to_agent", agent2,
                "correlation_id", UUID.randomUUID().toString(), "payload", p2), RequestOptions.none());
        String s2id = (String) c2.get("intent_id");
        String s2 = waitForDone(client, s2id, 60_000);
        System.out.printf("step 2 → %s%n", s2);

        System.out.println("\n=== Manual Multi-Step Pipeline ===");
        System.out.printf("  Step 1 (compliance): %s  id=%s%n", s1, s1id);
        System.out.printf("  Step 2 (risk):       %s  id=%s%n", s2, s2id);
        boolean ok = ("COMPLETED".equals(s1) || "IN_PROGRESS".equals(s1)) && ("COMPLETED".equals(s2) || "IN_PROGRESS".equals(s2));
        System.out.println("  Result: " + (ok ? "ALL STEPS PASSED" : "PIPELINE FAILED"));
    }

    @SuppressWarnings("unchecked")
    static String waitForDone(AxmeClient client, String intentId, long timeoutMs) throws Exception {
        int since = 0; long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            Map<String, Object> events = client.listIntentEvents(intentId, since, RequestOptions.none());
            for (Map<String, Object> evt : (List<Map<String, Object>>) events.getOrDefault("events", List.of())) {
                String status = SseHelper.str(evt, "status");
                if (evt.get("seq") instanceof Number n) since = Math.max(since, n.intValue());
                if (Set.of("COMPLETED", "IN_PROGRESS", "FAILED", "CANCELED", "TIMED_OUT").contains(status)) return status;
            }
            Thread.sleep(1000);
        }
        return "UNKNOWN";
    }
}
