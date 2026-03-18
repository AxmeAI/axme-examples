package ai.axme.examples.internal;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Risk Assessment Agent — internal/notification example (Java). */
public class NotificationAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "risk-assessment-agent");

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("risk-assessment-agent starting  address=%s%n", ADDR);
        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id"); Number seq = (Number) d.get("seq");
                    if (seq != null) since = Math.max(since, seq.intValue()); if (id.isEmpty()) continue;
                    Map<String, Object> intent = SseHelper.unwrapIntent(client.getIntent(id, RequestOptions.none()));
                    if (!SseHelper.isActionable(intent)) continue;
                    Map<String, Object> p = SseHelper.effectivePayload(intent);

                    String ver = SseHelper.str(p, "version", "0.0.0"), env = SseHelper.str(p, "environment");
                    int cc = p.get("change_count") instanceof Number n ? n.intValue() : 0;
                    int thresh = p.get("risk_threshold") instanceof Number n ? n.intValue() : 30;
                    String[] parts = ver.split("\\."); int major = parts.length > 0 ? Integer.parseInt(parts[0]) : 0;
                    int minor = parts.length > 1 ? Integer.parseInt(parts[1]) : 0;

                    int score = 0; List<String> factors = new ArrayList<>();
                    if (major >= 4) { score += 40; factors.add("major bump +40"); }
                    else if (minor >= 5) { score += 15; factors.add("minor bump +15"); }
                    if (cc > 30) { score += 30; factors.add("high changes +30"); }
                    if ("production".equals(env)) { score += 25; factors.add("prod +25"); }
                    else if ("staging".equals(env) || "canary".equals(env)) { score += 10; factors.add("staging +10"); }
                    String level = score >= thresh ? "HIGH" : score >= thresh / 2 ? "MEDIUM" : "LOW";

                    client.resumeIntent(id, Map.of("action", "complete", "risk_score", score, "risk_level", level, "factors", factors),
                            SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s (risk=%s score=%d)%n", id, level, score);
                }
            } catch (Exception e) { Thread.sleep(2000); }
        }
    }
}
