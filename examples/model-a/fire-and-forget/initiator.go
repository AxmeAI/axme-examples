// Model A — Fire and Forget: send intent, disconnect, check later (Go).
//
// Run:
//
//	AXME_API_KEY=<workspace-key> AXME_TO_AGENT=agent://org/ws/compliance-checker-agent \
//	  go run examples/model-a/fire-and-forget/initiator.go
package main

import (
	"context"
	"log"
	"os"
	"time"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }

func main() {
	apiKey := os.Getenv("AXME_API_KEY")
	baseURL := envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	toAgent := os.Getenv("AXME_TO_AGENT")

	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	if toAgent == "" { log.Fatal("AXME_TO_AGENT is required") }

	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }
	ctx := context.Background()

	log.Printf("firing intent to %s ...", toAgent)
	created, err := client.CreateIntent(ctx, map[string]any{
		"intent_type": "intent.compliance.check.v1",
		"from_agent":  "initiator://fire-and-forget",
		"to_agent":    toAgent,
		"reply_to":    "initiator://fire-and-forget",
		"payload": map[string]any{
			"change_id": "CHG-FIRE-FORGET-001", "service": "payments-service", "version": "2.1.0",
			"environment": "staging", "change_type": "config_update", "risk_level": "medium",
		},
	}, axme.RequestOptions{})
	if err != nil { log.Fatalf("create_intent failed: %v", err) }

	intentID, _ := created["intent_id"].(string)
	log.Printf("intent sent: %s — disconnecting", intentID)
	log.Println("doing other work for 15 seconds...")
	time.Sleep(15 * time.Second)

	log.Println("checking intent status...")
	resp, err := client.GetIntent(ctx, intentID, axme.RequestOptions{})
	if err != nil { log.Fatalf("get_intent failed: %v", err) }

	intent, _ := resp["intent"].(map[string]any)
	if intent == nil { intent = resp }
	status := ""
	if s, ok := intent["lifecycle_status"].(string); ok { status = s }
	if status == "" { status, _ = intent["status"].(string) }

	log.Printf("intent %s → %s", intentID, status)
	if status == "COMPLETED" || status == "IN_PROGRESS" {
		log.Println("SUCCESS — fire-and-forget pattern verified")
	} else {
		log.Printf("status: %s (agent may still be processing)", status)
	}
}
