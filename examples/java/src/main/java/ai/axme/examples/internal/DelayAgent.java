package ai.axme.examples.internal;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Change Window Validator — internal/delay example (Java). */
public class DelayAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "change-window-validator");
    static final Set<String> WINDOWS = Set.of("MW-2026-Q1-01","MW-2026-Q1-02","MW-2026-Q1-03","MW-2026-Q1-04","MW-2026-Q1-05","MW-2026-Q1-06");
    static final Set<String> TYPES = Set.of("config_update","dependency_update","rollback","hotfix");

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("change-window-validator starting  address=%s%n", ADDR);
        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id"); Number seq = (Number) d.get("seq");
                    if (seq != null) since = Math.max(since, seq.intValue()); if (id.isEmpty()) continue;
                    Map<String, Object> intent = SseHelper.unwrapIntent(client.getIntent(id, RequestOptions.none()));
                    if (!SseHelper.isActionable(intent)) continue;
                    Map<String, Object> p = SseHelper.effectivePayload(intent);

                    String changeId = SseHelper.str(p, "change_id", "?"), env = SseHelper.str(p, "environment");
                    String type = SseHelper.str(p, "change_type"), windowId = SseHelper.str(p, "window_id");

                    Map<String, Object> res = new HashMap<>();
                    boolean ok = true; String reason = changeId + ": validated";
                    if (!TYPES.contains(type)) { ok = false; reason = changeId + ": change_type not allowed"; }
                    else if ("production".equals(env) && windowId.isEmpty()) { ok = false; reason = changeId + ": production requires window_id"; }
                    else if ("production".equals(env) && !WINDOWS.contains(windowId)) { ok = false; reason = changeId + ": window_id not approved"; }
                    if (ok && !windowId.isEmpty() && WINDOWS.contains(windowId)) { res.put("window_id", windowId); res.put("window_approved", true); }
                    res.put("action", ok ? "complete" : "fail"); res.put("allowed", ok); res.put("reason", reason);
                    client.resumeIntent(id, res, SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s (allowed=%s)%n", id, ok);
                }
            } catch (Exception e) { Thread.sleep(2000); }
        }
    }
}
