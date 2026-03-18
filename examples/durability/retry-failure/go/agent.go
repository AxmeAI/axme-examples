// Webhook Receiver Agent — durability/retry-failure example (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=webhook-receiver-agent
//	go run examples/durability/retry-failure/agent.go
package main

import (
	"context"
	"crypto/sha256"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

var (
	baseURL      = envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	apiKey       = os.Getenv("AXME_API_KEY")
	agentAddress = envOr("AXME_AGENT_ADDRESS", "webhook-receiver-agent")
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
func str(m map[string]any, k, d string) string { if v, ok := m[k].(string); ok { return v }; return d }

func processWebhook(p map[string]any) map[string]any {
	eventType := str(p, "event_type", "unknown")
	source := str(p, "source", "")
	testID := str(p, "test_id", "")
	fp := fmt.Sprintf("%x", sha256.Sum256([]byte(eventType+":"+source+":"+testID)))[:16]
	return map[string]any{"event_type": eventType, "source": source, "fingerprint": fp, "processed": true,
		"note": fmt.Sprintf("webhook event '%s' processed from '%s'", eventType, source)}
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	log.Printf("webhook-receiver starting  address=%s  binding=stream", agentAddress)

	intents, errs := client.Listen(ctx, agentAddress, axme.ListenOptions{})
	for {
		select {
		case d, ok := <-intents:
			if !ok { return }
			id := str(d, "intent_id", ""); if id == "" { continue }
			resp, _ := client.GetIntent(ctx, id, axme.RequestOptions{})
			intent, _ := resp["intent"].(map[string]any); if intent == nil { intent = resp }
			status := strings.ToUpper(str(intent, "lifecycle_status", str(intent, "status", "")))
			if !map[string]bool{"CREATED": true, "DELIVERED": true, "ACKNOWLEDGED": true, "IN_PROGRESS": true, "WAITING": true}[status] { continue }
			raw, _ := intent["payload"].(map[string]any); if raw == nil { raw = map[string]any{} }
			eff, _ := raw["parent_payload"].(map[string]any); if eff == nil { eff = raw }

			result := processWebhook(eff)
			result["action"] = "complete"
			log.Printf("processed webhook for %s: fingerprint=%s", id, result["fingerprint"])
			client.ResumeIntent(ctx, id, result, axme.RequestOptions{OwnerAgent: agentAddress})
			log.Printf("resumed %s", id)
		case err, ok := <-errs: if !ok { return }; log.Printf("error: %v", err)
		case <-ctx.Done(): return
		}
	}
}
