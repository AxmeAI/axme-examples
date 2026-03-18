package ai.axme.examples.human;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Budget Envelope Validator — human/email example (Java). */
public class EmailAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "budget-envelope-validator");
    static final Map<String, Double> ENVELOPES = Map.of(
            "cloud_infrastructure", 50000.0, "software_licenses", 20000.0,
            "contractor_services", 40000.0, "hardware", 15000.0);

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("budget-envelope-validator starting  address=%s%n", ADDR);
        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id"); Number seq = (Number) d.get("seq");
                    if (seq != null) since = Math.max(since, seq.intValue()); if (id.isEmpty()) continue;
                    Map<String, Object> intent = SseHelper.unwrapIntent(client.getIntent(id, RequestOptions.none()));
                    if (!SseHelper.isActionable(intent)) continue;
                    Map<String, Object> p = SseHelper.effectivePayload(intent);

                    double amount = p.get("amount") instanceof Number n ? n.doubleValue() : 0;
                    String category = SseHelper.str(p, "category"), currency = SseHelper.str(p, "currency", "USD");
                    Double envelope = ENVELOPES.get(category);

                    Map<String, Object> res = new HashMap<>();
                    if (envelope == null) { res.put("action", "fail"); res.put("within_envelope", false); res.put("reason", "unknown category"); }
                    else if (amount > envelope) { res.put("action", "fail"); res.put("within_envelope", false); res.put("reason", "exceeds envelope"); }
                    else {
                        double headroom = Math.round((envelope - amount) / envelope * 1000.0) / 10.0;
                        res.put("action", "complete"); res.put("within_envelope", true);
                        res.put("reason", String.format("%s %.0f within %s envelope (%.1f%% headroom)", currency, amount, category, headroom));
                        res.put("envelope", envelope); res.put("headroom_pct", headroom);
                    }
                    client.resumeIntent(id, res, SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s (within_envelope=%s)%n", id, res.get("within_envelope"));
                }
            } catch (Exception e) { Thread.sleep(2000); }
        }
    }
}
