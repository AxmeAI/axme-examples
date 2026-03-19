// Clarification — human/clarification example (Go).
//
// Creates an intent with a human clarification step. The workflow pauses
// and emails the assignee a link to provide missing information or decline.
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
	notifyEmail := envOr("AXME_NOTIFY_EMAIL", "cs@example.com")

	if apiKey == "" {
		log.Fatal("AXME_API_KEY is required")
	}

	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil {
		log.Fatalf("client init: %v", err)
	}

	ctx := context.Background()

	log.Println("creating clarification intent ...")
	created, err := client.CreateIntent(ctx, map[string]any{
		"intent_type": "intent.customer.clarification.v1",
		"from_agent":  "initiator://human-clarification",
		"to_agent":    "agent://agent_core",
		"payload": map[string]any{
			"customer": "ABC Corp",
			"ticket":   "ONBOARD-429",
		},
		"human_task": map[string]any{
			"title":            "Clarification needed \u2014 ABC Corp onboarding",
			"description":     "Ticket ONBOARD-429 for ABC Corp requires additional information before onboarding can proceed. Please provide the requested details or decline.",
			"task_type":        "clarification",
			"notify_email":    notifyEmail,
			"allowed_outcomes": []string{"provided", "declined"},
			"required_comment": true,
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
