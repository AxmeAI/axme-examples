package ai.axme.examples.delivery;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Fulfillment Service Agent — inbox/reply_to delivery (Java). */
public class InboxAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "fulfillment-service-agent");
    static final Map<String, String> SHIPPING = Map.of("express", "1-2 business days", "standard", "3-5 business days", "economy", "7-10 business days");

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("fulfillment-service-agent starting  address=%s%n", ADDR);
        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id");
                    Number seq = (Number) d.get("seq"); if (seq != null) since = Math.max(since, seq.intValue());
                    if (id.isEmpty()) continue;
                    Map<String, Object> intent = client.getIntent(id, RequestOptions.none());
                    @SuppressWarnings("unchecked") Map<String, Object> p = (Map<String, Object>) intent.getOrDefault("payload", Map.of());
                    String orderId = SseHelper.str(p, "order_id"); String shipping = SseHelper.str(p, "shipping", "standard");
                    @SuppressWarnings("unchecked") List<Map<String, Object>> items = (List<Map<String, Object>>) p.getOrDefault("items", List.of());

                    Map<String, Object> res = new HashMap<>();
                    if (orderId.isEmpty()) { res.put("action", "fail"); res.put("reason", "order_id is required"); }
                    else if (items.isEmpty()) { res.put("action", "fail"); res.put("reason", "items list is empty"); }
                    else if (!SHIPPING.containsKey(shipping)) { res.put("action", "fail"); res.put("reason", "unknown shipping"); }
                    else {
                        int total = items.stream().mapToInt(i -> i.get("quantity") instanceof Number n ? n.intValue() : 0).sum();
                        res.put("action", "complete"); res.put("fulfillment_id", "FUL-" + String.format("%05d", Math.abs((orderId + SseHelper.str(p, "customer_id")).hashCode()) % 100000));
                        res.put("tracking_number", "AXME-" + orderId.toUpperCase() + "-" + String.format("%04d", Math.abs(orderId.hashCode()) % 10000));
                        res.put("warehouse", "WH-US-EAST-1"); res.put("shipping_method", shipping); res.put("eta", SHIPPING.get(shipping));
                        res.put("items_shipped", total); res.put("status", "fulfilled");
                    }
                    client.resumeIntent(id, res, SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s action=%s%n", id, res.get("action"));
                }
            } catch (Exception e) { Thread.sleep(2000); }
        }
    }
}
