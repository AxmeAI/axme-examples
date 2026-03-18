package ai.axme.examples;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.*;

/**
 * Shared SSE helper for agent intent stream polling.
 * The Java SDK does not include a built-in SSE/listen method,
 * so this helper provides a minimal SSE client for the agent inbox stream.
 */
public final class SseHelper {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private SseHelper() {}

    /**
     * Poll the agent intent stream (SSE endpoint).
     * Returns parsed intent deliveries from the stream.
     */
    public static List<Map<String, Object>> pollAgentStream(
            String baseUrl, String apiKey, String agentAddress,
            int since, int waitSeconds) throws Exception {

        String path = agentAddress.startsWith("agent://")
                ? agentAddress.substring("agent://".length()) : agentAddress;
        String url = baseUrl + "/v1/agents/" + path + "/intents/stream"
                + "?since=" + since + "&wait_seconds=" + waitSeconds;

        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setRequestProperty("x-api-key", apiKey);
        conn.setRequestProperty("Accept", "text/event-stream");
        conn.setConnectTimeout(5000);
        conn.setReadTimeout((waitSeconds + 5) * 1000);

        List<Map<String, Object>> results = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(conn.getInputStream()))) {
            String eventType = "";
            StringBuilder data = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.startsWith("event: ")) {
                    eventType = line.substring(7).trim();
                } else if (line.startsWith("data: ")) {
                    data.append(line.substring(6));
                } else if (line.isEmpty() && data.length() > 0) {
                    if (eventType.startsWith("intent.")) {
                        results.add(parseJson(data.toString()));
                    }
                    eventType = "";
                    data.setLength(0);
                }
            }
        }
        return results;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> parseJson(String json) {
        try {
            return MAPPER.readValue(json, Map.class);
        } catch (Exception e) {
            return Map.of();
        }
    }

    public static String env(String key, String def) {
        String v = System.getenv(key);
        return v != null && !v.isEmpty() ? v : def;
    }

    public static String str(Map<String, Object> m, String key) {
        return str(m, key, "");
    }

    public static String str(Map<String, Object> m, String key, String def) {
        Object v = m.get(key);
        return v instanceof String s && !s.isEmpty() ? s : def;
    }

    /** Extract effective payload (handles step-intent wrapping). */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> effectivePayload(Map<String, Object> intent) {
        Map<String, Object> raw = intent.containsKey("payload")
                ? (Map<String, Object>) intent.get("payload") : Map.of();
        if (raw == null) raw = Map.of();
        Object pp = raw.get("parent_payload");
        return pp instanceof Map ? (Map<String, Object>) pp : raw;
    }

    /** Unwrap intent from response. */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> unwrapIntent(Map<String, Object> resp) {
        Object i = resp.get("intent");
        return i instanceof Map ? (Map<String, Object>) i : resp;
    }

    /** Check if intent status is actionable. */
    public static boolean isActionable(Map<String, Object> intent) {
        String status = str(intent, "lifecycle_status");
        if (status.isEmpty()) status = str(intent, "status");
        return Set.of("CREATED", "DELIVERED", "ACKNOWLEDGED", "IN_PROGRESS", "WAITING")
                .contains(status.toUpperCase());
    }

    /** Create RequestOptions with owner_agent set. */
    public static dev.axme.sdk.RequestOptions withOwner(String ownerAgent) {
        return new dev.axme.sdk.RequestOptions(null, null, ownerAgent, null, null);
    }
}
