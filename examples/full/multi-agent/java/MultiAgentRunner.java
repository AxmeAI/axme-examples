package ai.axme.examples.full;

import ai.axme.examples.SseHelper;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.File;
import java.util.*;

/** Run both agents for the full multi-agent scenario (Java). */
public class MultiAgentRunner {
    public static void main(String[] args) throws Exception {
        System.out.println("Starting agents for full/multi-agent scenario...\n");
        // In Java, running multiple agent mains requires separate processes or threads.
        // Here we use threads for simplicity — each agent's main runs in its own thread.

        String[][] agents = {
                {"compliance-checker", "ai.axme.examples.delivery.StreamAgent", "compliance-checker-agent"},
                {"risk-assessment", "ai.axme.examples.internal.NotificationAgent", "risk-assessment-agent"},
        };

        List<Thread> threads = new ArrayList<>();
        for (String[] a : agents) {
            String key = loadApiKey(a[0]);
            if (key.isEmpty()) key = System.getenv("AXME_API_KEY");
            if (key == null || key.isEmpty()) {
                System.err.printf("[warn] no API key for '%s'%n", a[0]);
                continue;
            }

            // Set env vars via system properties (agent code reads System.getenv)
            // Note: System.setenv is not possible in Java; agents should read from a shared config
            System.out.printf("[agent]  %s — %s%n", a[2], a[1]);
            String finalKey = key;
            Thread t = new Thread(() -> {
                try {
                    // For a real multi-agent setup, launch separate JVM processes.
                    // This demo shows the pattern — real deployment uses separate processes.
                    System.out.printf("Agent %s would start with key=%s...%n", a[2], finalKey.substring(0, 10) + "...");
                } catch (Exception e) { e.printStackTrace(); }
            }, a[2]);
            t.setDaemon(true);
            t.start();
            threads.add(t);
        }

        System.out.println("\nBoth agents configured. In production, run each agent as a separate process.");
        System.out.println("Example:");
        System.out.println("  AXME_API_KEY=<key1> AXME_AGENT_ADDRESS=compliance-checker-agent mvn exec:java -Dexec.mainClass=ai.axme.examples.delivery.StreamAgent");
        System.out.println("  AXME_API_KEY=<key2> AXME_AGENT_ADDRESS=risk-assessment-agent mvn exec:java -Dexec.mainClass=ai.axme.examples.internal.NotificationAgent");
    }

    @SuppressWarnings("unchecked")
    static String loadApiKey(String nameFragment) {
        try {
            String home = System.getProperty("user.home");
            File f = new File(home, ".config/axme/scenario-agents.json");
            Map<String, Object> data = new ObjectMapper().readValue(f, Map.class);
            for (Map<String, Object> agent : (List<Map<String, Object>>) data.getOrDefault("agents", List.of())) {
                String addr = (String) agent.getOrDefault("address", "");
                if (addr.contains(nameFragment)) return (String) agent.getOrDefault("api_key", "");
            }
        } catch (Exception ignored) {}
        return "";
    }
}
