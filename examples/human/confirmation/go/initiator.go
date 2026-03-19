// Confirmation — human/confirmation example (Go).
//
// Creates an intent with a human confirmation step. The workflow pauses
// and emails the assignee a link to confirm or deny DNS propagation.
//
// Run:
//
//	AXME_API_KEY=<key> go run initiator.go
package main

import (
	"context"
	"log"
	"os"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

func main() {
	apiKey := os.Getenv("AXME_API_KEY")
	baseURL := envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	notifyEmail := envOr("AXME_NOTIFY_EMAIL", "ops@example.com")

	if apiKey == "" {
		log.Fatal("AXME_API_KEY is required")
	}

	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil {
		log.Fatalf("client init: %v", err)
	}

	ctx := context.Background()

	log.Println("creating confirmation intent ...")
	created, err := client.CreateIntent(ctx, map[string]any{
		"intent_type": "intent.dns.confirmation.v1",
		"from_agent":  "initiator://human-confirmation",
		"to_agent":    "agent://agent_core",
		"payload": map[string]any{
			"domain":      "api.example.com",
			"record_type": "CNAME",
			"new_value":   "new-lb.example.com",
		},
		"human_task": map[string]any{
			"title":            "Confirm DNS propagation",
			"description":     "DNS change submitted: api.example.com CNAME -> new-lb.example.com. Please verify propagation is complete.",
			"task_type":        "confirmation",
			"notify_email":    notifyEmail,
			"allowed_outcomes": []string{"confirmed", "denied"},
		},
	}, axme.RequestOptions{})
	if err != nil {
		log.Fatalf("create_intent failed: %v", err)
	}

	intentID, _ := created["intent_id"].(string)
	log.Printf("intent created: %s", intentID)
	log.Println("Check your email for the task link.")
}

func envOr(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}
