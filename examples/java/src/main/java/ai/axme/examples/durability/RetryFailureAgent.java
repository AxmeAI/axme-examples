package ai.axme.examples.durability;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.security.MessageDigest;
import java.util.*;

/** Webhook Receiver Agent — durability/retry-failure (Java). */
public class RetryFailureAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "webhook-receiver-agent");

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("webhook-receiver starting  address=%s%n", ADDR);
        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id"); Number seq = (Number) d.get("seq");
                    if (seq != null) since = Math.max(since, seq.intValue()); if (id.isEmpty()) continue;
                    Map<String, Object> intent = SseHelper.unwrapIntent(client.getIntent(id, RequestOptions.none()));
                    if (!SseHelper.isActionable(intent)) continue;
                    Map<String, Object> p = SseHelper.effectivePayload(intent);

                    String et = SseHelper.str(p, "event_type", "unknown"), src = SseHelper.str(p, "source");
                    String tid = SseHelper.str(p, "test_id");
                    MessageDigest md = MessageDigest.getInstance("SHA-256");
                    String fp = bytesToHex(md.digest((et + ":" + src + ":" + tid).getBytes())).substring(0, 16);

                    client.resumeIntent(id, Map.of("action", "complete", "event_type", et, "source", src,
                            "fingerprint", fp, "processed", true, "note", "webhook processed"), SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s fingerprint=%s%n", id, fp);
                }
            } catch (Exception e) { Thread.sleep(2000); }
        }
    }

    static String bytesToHex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte v : b) sb.append(String.format("%02x", v));
        return sb.toString();
    }
}
