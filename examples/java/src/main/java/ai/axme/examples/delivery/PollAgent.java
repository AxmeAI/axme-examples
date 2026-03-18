package ai.axme.examples.delivery;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Batch Processor Agent — poll delivery binding (Java). */
public class PollAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "batch-processor-agent");
    static final int INTERVAL = Integer.parseInt(SseHelper.env("POLL_INTERVAL", "10")) * 1000;

    static final Map<String, Integer> RECORD_COUNTS = Map.of(
            "transactions", 14203, "invoices", 1847, "orders", 3291, "events", 82014);

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("batch-processor-agent starting  address=%s  binding=poll  interval=%dms%n", ADDR, INTERVAL);
        Set<String> seen = new HashSet<>();

        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, 0, 2)) {
                    String id = SseHelper.str(d, "intent_id");
                    if (id.isEmpty() || seen.contains(id)) continue;
                    seen.add(id);

                    Map<String, Object> intent = client.getIntent(id, RequestOptions.none());
                    Map<String, Object> p = (intent.get("payload") instanceof Map) ? (Map<String, Object>) intent.get("payload") : Map.of();

                    String batchId = SseHelper.str(p, "batch_id", "?");
                    String recordType = SseHelper.str(p, "record_type");
                    String dateRange = SseHelper.str(p, "date_range");

                    Map<String, Object> res = new HashMap<>();
                    if (batchId.equals("?")) { res.put("action", "fail"); res.put("reason", "batch_id is required"); }
                    else if (!RECORD_COUNTS.containsKey(recordType)) { res.put("action", "fail"); res.put("reason", "unsupported record_type"); }
                    else if (dateRange.isEmpty()) { res.put("action", "fail"); res.put("reason", "date_range is required"); }
                    else { res.put("action", "complete"); res.put("batch_id", batchId); res.put("record_type", recordType);
                        res.put("date_range", dateRange); res.put("record_count", RECORD_COUNTS.get(recordType)); res.put("status", "processed"); }

                    client.resumeIntent(id, res, SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s action=%s%n", id, res.get("action"));
                }
            } catch (Exception e) { /* timeout normal */ }
            Thread.sleep(INTERVAL);
        }
    }
}
