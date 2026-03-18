package ai.axme.examples.delivery;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Compliance Checker Agent — stream delivery binding (Java). */
public class StreamAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "compliance-checker-agent");

    static final Set<String> BLOCKED = Set.of("production");
    static final Set<String> RISK_BACKUP = Set.of("high", "critical");

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("compliance-checker-agent starting  address=%s  binding=stream%n", ADDR);

        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id");
                    Number seq = (Number) d.get("seq");
                    if (seq != null) since = Math.max(since, seq.intValue());
                    if (id.isEmpty()) continue;

                    Map<String, Object> intent = SseHelper.unwrapIntent(client.getIntent(id, RequestOptions.none()));
                    if (!SseHelper.isActionable(intent)) continue;
                    Map<String, Object> p = SseHelper.effectivePayload(intent);

                    String changeId = SseHelper.str(p, "change_id", "?");
                    String env = SseHelper.str(p, "environment");
                    String risk = SseHelper.str(p, "risk_level", "low");
                    boolean backup = Boolean.TRUE.equals(p.get("backup_confirmed"));

                    boolean passed; String reason;
                    if (BLOCKED.contains(env)) { passed = false; reason = changeId + ": production changes require manual approval"; }
                    else if (RISK_BACKUP.contains(risk) && !backup) { passed = false; reason = changeId + ": risk_level=" + risk + " requires backup_confirmed=true"; }
                    else { passed = true; reason = changeId + ": compliance checks passed"; }

                    Map<String, Object> res = new HashMap<>();
                    res.put("action", passed ? "complete" : "fail"); res.put("passed", passed); res.put("reason", reason);
                    if (passed) res.put("checked_fields", List.of("environment", "risk_level", "backup_confirmed"));
                    client.resumeIntent(id, res, SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s (passed=%s)%n", id, passed);
                }
            } catch (Exception e) { System.err.println("stream error: " + e.getMessage()); Thread.sleep(2000); }
        }
    }
}
