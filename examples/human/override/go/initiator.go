// Override — human/override example (Go).
//
// Creates an intent with a human override step. The workflow pauses
// and emails the senior operator a link to approve or reject a deployment
// freeze override with justification.
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
	notifyEmail := envOr("AXME_NOTIFY_EMAIL", "senior-ops@example.com")

	if apiKey == "" {
		log.Fatal("AXME_API_KEY is required")
	}

	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil {
		log.Fatalf("client init: %v", err)
	}

	ctx := context.Background()

	log.Println("creating override intent ...")
	created, err := client.CreateIntent(ctx, map[string]any{
		"intent_type": "intent.deploy.override.v1",
		"from_agent":  "initiator://human-override",
		"to_agent":    "agent://agent_core",
		"payload": map[string]any{
			"service": "api-gateway",
			"version": "v3.5.0",
			"ticket":  "CHG-2026-892",
		},
		"human_task": map[string]any{
			"title":            "Override deployment freeze",
			"description":     "Deployment of api-gateway v3.5.0 is blocked by a deployment freeze (ticket CHG-2026-892). A senior operator must approve the override with justification or reject.",
			"task_type":        "override",
			"notify_email":    notifyEmail,
			"allowed_outcomes": []string{"override_approved", "rejected"},
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
