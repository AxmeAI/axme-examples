package ai.axme.examples.human;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;

/** Access Policy Checker — human/form example (Java). */
public class FormAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "access-policy-checker");
    static final Set<String> ALLOWED_ACCESS = Set.of("READ", "READ_WRITE");
    static final Set<String> PII_BLOCKED = Set.of("READ_WRITE", "WRITE", "ADMIN");
    static final Set<String> SIGNOFF_RES = Set.of("prod-analytics-db", "prod-customer-db", "prod-payments-db");

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("access-policy-checker starting  address=%s%n", ADDR);
        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id"); Number seq = (Number) d.get("seq");
                    if (seq != null) since = Math.max(since, seq.intValue()); if (id.isEmpty()) continue;
                    Map<String, Object> intent = SseHelper.unwrapIntent(client.getIntent(id, RequestOptions.none()));
                    if (!SseHelper.isActionable(intent)) continue;
                    Map<String, Object> p = SseHelper.effectivePayload(intent);

                    String access = SseHelper.str(p, "access_type").toUpperCase(), requestor = SseHelper.str(p, "requestor");
                    boolean pii = Boolean.TRUE.equals(p.get("pii_fields"));
                    List<String> checks = new ArrayList<>(), violations = new ArrayList<>();

                    if (ALLOWED_ACCESS.contains(access)) checks.add("access type ok"); else violations.add("access type not allowed");
                    if (!requestor.isEmpty()) checks.add("requestor present"); else violations.add("requestor missing");
                    if (pii && PII_BLOCKED.contains(access)) violations.add("PII write blocked");
                    else if (pii) checks.add("PII read-only ok"); else checks.add("no PII");

                    boolean ok = violations.isEmpty();
                    Map<String, Object> res = new HashMap<>();
                    res.put("action", ok ? "complete" : "fail"); res.put("policy_passed", ok);
                    res.put("passed_checks", checks); res.put("violations", violations);
                    if (ok) res.put("requires_human_signoff", SIGNOFF_RES.contains(SseHelper.str(p, "resource")));
                    client.resumeIntent(id, res, SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s (passed=%s)%n", id, ok);
                }
            } catch (Exception e) { Thread.sleep(2000); }
        }
    }
}
