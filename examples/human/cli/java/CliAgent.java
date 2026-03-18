package ai.axme.examples.human;

import ai.axme.examples.SseHelper;
import dev.axme.sdk.*;
import java.util.*;
import java.util.regex.Pattern;

/** Deploy Readiness Checker — human/cli example (Java). */
public class CliAgent {
    static final String BASE = SseHelper.env("AXME_BASE_URL", "https://api.cloud.axme.ai");
    static final String KEY = System.getenv("AXME_API_KEY");
    static final String ADDR = SseHelper.env("AXME_AGENT_ADDRESS", "deploy-readiness-checker");
    static final Pattern SEMVER = Pattern.compile("^\\d+\\.\\d+\\.\\d+$");
    static final Set<String> ENVS = Set.of("staging", "canary", "preview");

    public static void main(String[] args) throws Exception {
        if (KEY == null || KEY.isEmpty()) { System.err.println("AXME_API_KEY is required"); System.exit(1); }
        AxmeClient client = new AxmeClient(new AxmeClientConfig(BASE, KEY));
        System.out.printf("deploy-readiness-checker starting  address=%s%n", ADDR);
        int since = 0;
        while (true) {
            try {
                for (Map<String, Object> d : SseHelper.pollAgentStream(BASE, KEY, ADDR, since, 15)) {
                    String id = SseHelper.str(d, "intent_id"); Number seq = (Number) d.get("seq");
                    if (seq != null) since = Math.max(since, seq.intValue()); if (id.isEmpty()) continue;
                    Map<String, Object> intent = SseHelper.unwrapIntent(client.getIntent(id, RequestOptions.none()));
                    if (!SseHelper.isActionable(intent)) continue;
                    Map<String, Object> p = SseHelper.effectivePayload(intent);

                    String ver = SseHelper.str(p, "version"), env = SseHelper.str(p, "environment");
                    String rb = SseHelper.str(p, "rollback_tag"), svc = SseHelper.str(p, "service");
                    List<String> passed = new ArrayList<>(), fail = new ArrayList<>();
                    if (SEMVER.matcher(ver).matches()) passed.add("version ok"); else fail.add("version invalid");
                    if (ENVS.contains(env)) passed.add("env ok"); else fail.add("env not allowed");
                    if (!rb.isEmpty()) passed.add("rollback set"); else fail.add("rollback missing");
                    if (!svc.isEmpty()) passed.add("service set"); else fail.add("service empty");

                    boolean ready = fail.isEmpty();
                    Map<String, Object> res = new HashMap<>();
                    res.put("action", ready ? "complete" : "fail"); res.put("ready", ready);
                    res.put("passed_checks", passed); res.put("failures", fail);
                    client.resumeIntent(id, res, SseHelper.withOwner(ADDR));
                    System.out.printf("resumed %s (ready=%s)%n", id, ready);
                }
            } catch (Exception e) { Thread.sleep(2000); }
        }
    }
}
