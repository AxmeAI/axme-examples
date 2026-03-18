// Compliance Checker Agent — stream delivery binding (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=compliance-checker-agent
//	go run examples/delivery/stream/agent.go
package main

import (
	"context"
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
	agentAddress = envOr("AXME_AGENT_ADDRESS", "compliance-checker-agent")
)

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// --- Business logic ---

var (
	blockedEnvironments  = map[string]bool{"production": true}
	riskRequiresBackup   = map[string]bool{"high": true, "critical": true}
)

func checkCompliance(payload map[string]any) (bool, string) {
	changeID := str(payload, "change_id", "?")
	environment := str(payload, "environment", "")
	riskLevel := str(payload, "risk_level", "low")
	backupOk, _ := payload["backup_confirmed"].(bool)

	if blockedEnvironments[environment] {
		return false, fmt.Sprintf("%s: production changes require manual approval, not automated", changeID)
	}
	if riskRequiresBackup[riskLevel] && !backupOk {
		return false, fmt.Sprintf("%s: risk_level=%s requires backup_confirmed=true", changeID, riskLevel)
	}
	return true, fmt.Sprintf("%s: compliance checks passed (environment=%s, risk=%s)", changeID, environment, riskLevel)
}

func str(m map[string]any, key, def string) string {
	if v, ok := m[key].(string); ok && v != "" {
		return v
	}
	return def
}

func main() {
	if apiKey == "" {
		log.Fatal("AXME_API_KEY is required")
	}

	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil {
		log.Fatalf("client init failed: %v", err)
	}

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()

	log.Printf("compliance-checker-agent starting  address=%s  binding=stream", agentAddress)

	intents, errs := client.Listen(ctx, agentAddress, axme.ListenOptions{})
	for {
		select {
		case delivery, ok := <-intents:
			if !ok {
				return
			}
			intentID := str(delivery, "intent_id", "")
			if intentID == "" {
				continue
			}
			log.Printf("received intent %s", intentID)
			handleIntent(ctx, client, intentID)
		case err, ok := <-errs:
			if !ok {
				return
			}
			log.Printf("stream error: %v", err)
		case <-ctx.Done():
			log.Println("shutting down")
			return
		}
	}
}

func handleIntent(ctx context.Context, client *axme.Client, intentID string) {
	resp, err := client.GetIntent(ctx, intentID, axme.RequestOptions{})
	if err != nil {
		log.Printf("get_intent(%s) failed: %v", intentID, err)
		return
	}
	intent, _ := resp["intent"].(map[string]any)
	if intent == nil {
		intent = resp
	}

	status := strings.ToUpper(str(intent, "lifecycle_status", str(intent, "status", "")))
	actionable := map[string]bool{"CREATED": true, "DELIVERED": true, "ACKNOWLEDGED": true, "IN_PROGRESS": true, "WAITING": true}
	if !actionable[status] {
		return
	}

	rawPayload, _ := intent["payload"].(map[string]any)
	if rawPayload == nil {
		rawPayload = map[string]any{}
	}
	effectivePayload, _ := rawPayload["parent_payload"].(map[string]any)
	if effectivePayload == nil {
		effectivePayload = rawPayload
	}

	passed, reason := checkCompliance(effectivePayload)
	log.Printf("compliance result for %s: passed=%v  reason=%s", intentID, passed, reason)

	var resumePayload map[string]any
	if passed {
		resumePayload = map[string]any{
			"action": "complete", "passed": true, "reason": reason,
			"checked_fields": []string{"environment", "risk_level", "backup_confirmed"},
		}
	} else {
		resumePayload = map[string]any{"action": "fail", "passed": false, "reason": reason}
	}

	_, err = client.ResumeIntent(ctx, intentID, resumePayload, axme.RequestOptions{OwnerAgent: agentAddress})
	if err != nil {
		log.Printf("resume_intent(%s) failed: %v", intentID, err)
		return
	}
	log.Printf("resumed intent %s  (passed=%v)", intentID, passed)
}
