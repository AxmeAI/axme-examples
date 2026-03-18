package ai.axme.examples.delivery;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import com.sun.net.httpserver.*;

import java.io.*;
import java.net.InetSocketAddress;
import java.util.*;

/** Order Processing Agent — HTTP delivery binding (Java). */
public class HttpAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "http-order-processor");
    static final int PORT = Integer.parseInt(SseHelper.env("PORT", "8080"));
    static final Set<String> CURRENCIES = Set.of("USD", "EUR", "GBP", "JPY");

    static AxmeClient client;

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        client = new AxmeClient(new AxmeClientConfig(BASE, KEY));

        HttpServer server = HttpServer.create(new InetSocketAddress(PORT), 0);
        server.createContext("/health", ex -> { ex.sendResponseHeaders(200, 15); ex.getResponseBody().write("{\"status\":\"ok\"}".getBytes()); ex.close(); });
        server.createContext("/intent", ex -> {
            if (!"POST".equals(ex.getRequestMethod())) { ex.sendResponseHeaders(405, -1); ex.close(); return; }
            byte[] body = ex.getRequestBody().readAllBytes();
            ex.sendResponseHeaders(200, 10); ex.getResponseBody().write("{\"ack\":true}".getBytes()); ex.close();
            Map<String, Object> envelope = SseHelper.parseJson(new String(body));
            String id = SseHelper.str(envelope, "intent_id");
            if (!id.isEmpty()) new Thread(() -> handleAsync(id)).start();
        });
        server.start();
        System.out.printf("http-order-processor starting  port=%d%n", PORT);
    }

    static void handleAsync(String id) {
        try {
            Map<String, Object> intent = client.getIntent(id, RequestOptions.none());
            @SuppressWarnings("unchecked")
            Map<String, Object> p = (Map<String, Object>) intent.getOrDefault("payload", Map.of());
            String eventType = SseHelper.str(p, "event_type");
            String orderId = SseHelper.str(p, "order_id");
            double amount = p.get("amount") instanceof Number n ? n.doubleValue() : 0;
            String currency = SseHelper.str(p, "currency");

            Map<String, Object> res = new HashMap<>();
            if (!"order.placed".equals(eventType)) { res.put("action", "fail"); res.put("reason", "unexpected event_type"); }
            else if (orderId.isEmpty()) { res.put("action", "fail"); res.put("reason", "order_id is required"); }
            else if (!CURRENCIES.contains(currency)) { res.put("action", "fail"); res.put("reason", "unsupported currency"); }
            else {
                res.put("action", "complete"); res.put("order_id", orderId);
                res.put("tracking_id", "TRK-" + orderId.toUpperCase() + "-" + String.format("%05d", Math.abs(orderId.hashCode()) % 100000));
                res.put("status", "accepted"); res.put("currency", currency); res.put("amount", amount);
            }
            client.resumeIntent(id, res, SseHelper.withOwner(ADDR));
            System.out.printf("resumed %s action=%s%n", id, res.get("action"));
        } catch (Exception e) { System.err.println("handle error: " + e.getMessage()); }
    }
}
