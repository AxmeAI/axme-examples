// Assignment — human/assignment example (Go).
//
// Creates an intent with a human assignment step. The workflow pauses
// and emails the on-call manager a link to assign an incident commander.
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
	notifyEmail := envOr("AXME_NOTIFY_EMAIL", "oncall@example.com")

	if apiKey == "" {
		log.Fatal("AXME_API_KEY is required")
	}

	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil {
		log.Fatalf("client init: %v", err)
	}

	ctx := context.Background()

	log.Println("creating assignment intent ...")
	created, err := client.CreateIntent(ctx, map[string]any{
		"intent_type": "intent.incident.assignment.v1",
		"from_agent":  "initiator://human-assignment",
		"to_agent":    "agent://agent_core",
		"payload": map[string]any{
			"incident_id": "INC-2026-1847",
			"severity":    "P1",
			"service":     "payment-api",
		},
		"human_task": map[string]any{
			"title":            "Assign incident commander",
			"description":     "Incident INC-2026-1847 classified as P1 affecting payment-api. Please designate an incident commander.",
			"task_type":        "assignment",
			"notify_email":    notifyEmail,
			"allowed_outcomes": []string{"assigned", "declined"},
			"form_schema": map[string]any{
				"type":     "object",
				"required": []string{"assignee"},
				"properties": map[string]any{
					"assignee": map[string]any{"type": "string", "description": "Email of the designated incident commander"},
					"priority": map[string]any{"type": "string", "description": "Override priority level", "enum": []string{"P1", "P2", "P3", "P4"}},
				},
			},
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
