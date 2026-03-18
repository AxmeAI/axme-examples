// Model A — Simple Request: initiator waits for agent response (Go).
//
// Run:
//
//	AXME_API_KEY=<workspace-key> AXME_TO_AGENT=agent://org/ws/compliance-checker-agent \
//	  go run examples/model-a/simple-request/initiator.go
package main

import (
	"context"
	"crypto/rand"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

func newUUID() string {
	b := make([]byte, 16)
	rand.Read(b)
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:])
}

func main() {
	apiKey := os.Getenv("AXME_API_KEY")
	baseURL := envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	toAgent := os.Getenv("AXME_TO_AGENT")

	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	if toAgent == "" { log.Fatal("AXME_TO_AGENT is required") }

	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx := context.Background()

	log.Printf("creating intent to %s ...", toAgent)
	created, err := client.CreateIntent(ctx, map[string]any{
		"intent_type":    "intent.compliance.check.v1",
		"correlation_id": newUUID(),
		"from_agent":     "initiator://simple-request",
		"to_agent":       toAgent,
		"payload": map[string]any{
			"change_id": "CHG-MODEL-A-001", "service": "api-gateway", "version": "4.0.0",
			"environment": "staging", "change_type": "config_update", "risk_level": "low",
		},
	}, axme.RequestOptions{})
	if err != nil { log.Fatalf("create_intent failed: %v", err) }

	intentID, _ := created["intent_id"].(string)
	log.Printf("intent created: %s", intentID)
	log.Println("waiting for agent response...")

	deadline := time.After(120 * time.Second)
	since := 0
	sincePtr := &since
	for {
		select {
		case <-deadline:
			log.Fatal("timeout waiting for agent response")
		default:
		}

		events, err := client.ListIntentEvents(ctx, intentID, sincePtr, axme.RequestOptions{})
		if err != nil { time.Sleep(time.Second); continue }

		evtList, _ := events["events"].([]any)
		for _, e := range evtList {
			evt, _ := e.(map[string]any)
			status, _ := evt["status"].(string)
			if seq, ok := evt["seq"].(float64); ok { since = int(seq) }
			if status == "COMPLETED" || status == "IN_PROGRESS" || status == "FAILED" || status == "CANCELED" || status == "TIMED_OUT" {
				log.Printf("intent %s → %s", intentID, status)
				if status == "COMPLETED" || status == "IN_PROGRESS" { log.Println("SUCCESS — agent processed the request") }
				return
			}
		}
		time.Sleep(time.Second)
	}
}

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
