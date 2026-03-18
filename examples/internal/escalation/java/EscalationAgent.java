package ai.axme.examples.internal;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Incident Classifier Agent — internal/escalation example (Java). */
public class EscalationAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "incident-classifier-agent");
    static final Map<String, Integer> SLA = Map.of("P1", 5, "P2", 15, "P3", 60, "P4", 240);
    static final Set<String> CRITICAL = Set.of("api-gateway", "auth-service", "payments-processor");

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("incident-classifier starting  address=%s%n", ADDR);
        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id"); Number seq = (Number) d.get("seq");
                    if (seq != null) since = Math.max(since, seq.intValue()); if (id.isEmpty()) continue;
                    Map<String, Object> intent = SseHelper.unwrapIntent(client.getIntent(id, RequestOptions.none()));
                    if (!SseHelper.isActionable(intent)) continue;
                    Map<String, Object> p = SseHelper.effectivePayload(intent);

                    String incId = SseHelper.str(p, "incident_id", "?"), sev = SseHelper.str(p, "severity", "P3");
                    String svc = SseHelper.str(p, "service"), symptom = SseHelper.str(p, "symptom");
                    int sla = SLA.getOrDefault(sev, 60); boolean crit = CRITICAL.contains(svc);
                    List<String> affected = new ArrayList<>(); if (!svc.isEmpty()) affected.add(svc); if (crit) affected.add("downstream-dependents");
                    String esc = ("P1".equals(sev) || "P2".equals(sev)) && crit ? "on-call → team-lead → engineering-director" :
                            ("P1".equals(sev) || "P2".equals(sev)) ? "on-call → team-lead" : "on-call";

                    Map<String, Object> res = new HashMap<>();
                    res.put("action", "complete"); res.put("incident_id", incId); res.put("severity", sev);
                    res.put("is_critical_service", crit); res.put("affected_components", affected);
                    res.put("sla_minutes", sla); res.put("escalation_path", esc);
                    res.put("has_error_rate_signal", symptom.toLowerCase().contains("error rate") || symptom.contains("5xx"));
                    client.resumeIntent(id, res, SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s%n", id);
                }
            } catch (Exception e) { Thread.sleep(2000); }
        }
    }
}
