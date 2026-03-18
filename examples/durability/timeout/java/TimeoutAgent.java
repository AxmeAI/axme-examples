package ai.axme.examples.durability;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Slow Batch Processor — durability/timeout example (Java). */
public class TimeoutAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "slow-batch-processor");

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("slow-batch-processor starting  address=%s%n", ADDR);
        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id"); Number seq = (Number) d.get("seq");
                    if (seq != null) since = Math.max(since, seq.intValue()); if (id.isEmpty()) continue;
                    Map<String, Object> intent = SseHelper.unwrapIntent(client.getIntent(id, RequestOptions.none()));
                    if (!SseHelper.isActionable(intent)) continue;
                    Map<String, Object> p = SseHelper.effectivePayload(intent);

                    String batchId = SseHelper.str(p, "batch_id", "?");
                    int rc = p.get("record_count") instanceof Number n ? n.intValue() : 0;
                    Map<String, Object> res = new HashMap<>();
                    if (rc > 10000) { res.put("action", "fail"); res.put("batch_id", batchId); res.put("error", "batch too large: " + rc); }
                    else { res.put("action", "complete"); res.put("batch_id", batchId); res.put("record_count", rc); res.put("processed", true); }
                    client.resumeIntent(id, res, SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s action=%s%n", id, res.get("action"));
                }
            } catch (Exception e) { Thread.sleep(2000); }
        }
    }
}
