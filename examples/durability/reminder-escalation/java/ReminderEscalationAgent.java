package ai.axme.examples.durability;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Pre-Approval Validator — durability/reminder-escalation (Java). */
public class ReminderEscalationAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "pre-approval-validator");
    static final Set<String> TYPES = Set.of("config_update", "dependency_update", "rollback", "hotfix");
    static final Set<String> RISKS = Set.of("low", "medium", "high", "critical");

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("pre-approval-validator starting  address=%s%n", ADDR);
        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id"); Number seq = (Number) d.get("seq");
                    if (seq != null) since = Math.max(since, seq.intValue()); if (id.isEmpty()) continue;
                    Map<String, Object> intent = SseHelper.unwrapIntent(client.getIntent(id, RequestOptions.none()));
                    if (!SseHelper.isActionable(intent)) continue;
                    Map<String, Object> p = SseHelper.effectivePayload(intent);

                    String cid = SseHelper.str(p, "change_id", "?"), ct = SseHelper.str(p, "change_type");
                    String rl = SseHelper.str(p, "risk_level"), svc = SseHelper.str(p, "service");
                    boolean valid = true; String reason;
                    if (svc.isEmpty()) { valid = false; reason = cid + ": service is required"; }
                    else if (!TYPES.contains(ct)) { valid = false; reason = cid + ": change_type not allowed"; }
                    else if (!RISKS.contains(rl)) { valid = false; reason = cid + ": risk_level not valid"; }
                    else { reason = cid + ": pre-validation passed for " + svc; }

                    client.resumeIntent(id, Map.of("action", valid ? "complete" : "fail", "valid", valid, "reason", reason),
                            SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s (valid=%s)%n", id, valid);
                }
            } catch (Exception e) { Thread.sleep(2000); }
        }
    }
}
