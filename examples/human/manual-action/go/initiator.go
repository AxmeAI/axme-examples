// Manual action — human/manual-action example (Go).
//
// Creates an intent with a human manual-action step. The workflow pauses
// and emails the technician a link to report on a physical rack inspection.
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
	notifyEmail := envOr("AXME_NOTIFY_EMAIL", "dc-ops@example.com")

	if apiKey == "" {
		log.Fatal("AXME_API_KEY is required")
	}

	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil {
		log.Fatalf("client init: %v", err)
	}

	ctx := context.Background()

	log.Println("creating manual-action intent ...")
	created, err := client.CreateIntent(ctx, map[string]any{
		"intent_type": "intent.dc.manual_action.v1",
		"from_agent":  "initiator://human-manual-action",
		"to_agent":    "agent://agent_core",
		"payload": map[string]any{
			"rack_id":  "B-14",
			"location": "DC-East",
			"alert":    "elevated_temperature",
		},
		"human_task": map[string]any{
			"title":             "Inspect server rack B-14",
			"description":      "Elevated temperature alert in rack B-14 at DC-East. Please physically inspect the rack, check airflow and cooling, and report findings with evidence.",
			"task_type":         "manual_action",
			"notify_email":     notifyEmail,
			"allowed_outcomes":  []string{"completed", "failed"},
			"evidence_required": true,
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
