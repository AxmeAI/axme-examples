// Review — human/review example (Go).
//
// Creates an intent with a human review step. The workflow pauses
// and emails the reviewer a link to approve, request changes, or reject a PR.
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
	notifyEmail := envOr("AXME_NOTIFY_EMAIL", "reviewer@example.com")

	if apiKey == "" {
		log.Fatal("AXME_API_KEY is required")
	}

	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil {
		log.Fatalf("client init: %v", err)
	}

	ctx := context.Background()

	log.Println("creating review intent ...")
	created, err := client.CreateIntent(ctx, map[string]any{
		"intent_type": "intent.code.review.v1",
		"from_agent":  "initiator://human-review",
		"to_agent":    "agent://agent_core",
		"payload": map[string]any{
			"pr_number": 847,
			"title":     "Add retry logic to payment service",
			"author":    "alice",
		},
		"human_task": map[string]any{
			"title":            "Review PR #847",
			"description":     "PR #847 'Add retry logic to payment service' by alice is ready for review. Please approve, request changes, or reject.",
			"task_type":        "review",
			"notify_email":    notifyEmail,
			"allowed_outcomes": []string{"approved", "changes_requested", "rejected"},
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
