// Model A — Manual Multi-Step: chain two agents sequentially (Go).
//
// Run:
//
//	AXME_API_KEY=<workspace-key> \
//	AXME_AGENT_1=agent://org/ws/compliance-checker-agent \
//	AXME_AGENT_2=agent://org/ws/risk-assessment-agent \
//	  go run examples/model-a/manual-multi-step/initiator.go
package main

import (
	"context"
	"log"
	"os"
	"time"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }

func waitForDone(ctx context.Context, client *axme.Client, intentID string, timeout time.Duration) string {
	deadline := time.After(timeout)
	since := 0
	sincePtr := &since
	for {
		select {
		case <-deadline: return "TIMEOUT"
		default:
		}
		events, err := client.ListIntentEvents(ctx, intentID, sincePtr, axme.RequestOptions{})
		if err != nil { time.Sleep(time.Second); continue }
		evtList, _ := events["events"].([]any)
		for _, e := range evtList {
			evt, _ := e.(map[string]any)
			status, _ := evt["status"].(string)
			if seq, ok := evt["seq"].(float64); ok { since = int(seq) }
			if status == "COMPLETED" || status == "IN_PROGRESS" || status == "FAILED" || status == "CANCELED" || status == "TIMED_OUT" { return status }
		}
		time.Sleep(time.Second)
	}
}

func main() {
	apiKey := os.Getenv("AXME_API_KEY")
	baseURL := envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	agent1 := os.Getenv("AXME_AGENT_1")
	agent2 := os.Getenv("AXME_AGENT_2")

	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	if agent1 == "" || agent2 == "" { log.Fatal("AXME_AGENT_1 and AXME_AGENT_2 are required") }

	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }
	ctx := context.Background()

	changePayload := map[string]any{
		"change_id": "CHG-MULTI-STEP-001", "service": "api-gateway", "version": "5.0.0",
		"environment": "staging", "change_type": "config_update", "risk_level": "medium", "risk_threshold": 30,
	}

	// Step 1
	log.Printf("STEP 1: compliance check → %s", agent1)
	c1, err := client.CreateIntent(ctx, map[string]any{
		"intent_type": "intent.compliance.check.v1", "from_agent": "initiator://manual-multi-step",
		"to_agent": agent1, "payload": changePayload,
	}, axme.RequestOptions{})
	if err != nil { log.Fatalf("create step1 failed: %v", err) }
	step1ID, _ := c1["intent_id"].(string)
	log.Printf("step 1 intent: %s — waiting...", step1ID)
	step1Status := waitForDone(ctx, client, step1ID, 60*time.Second)
	log.Printf("step 1 → %s", step1Status)

	if step1Status != "COMPLETED" && step1Status != "IN_PROGRESS" {
		log.Fatalf("step 1 failed (%s) — aborting pipeline", step1Status)
	}

	// Step 2
	log.Printf("STEP 2: risk assessment → %s", agent2)
	step2Payload := map[string]any{}
	for k, v := range changePayload { step2Payload[k] = v }
	step2Payload["compliance_result"] = "passed"
	step2Payload["compliance_intent_id"] = step1ID

	c2, err := client.CreateIntent(ctx, map[string]any{
		"intent_type": "intent.risk.assessment.v1", "from_agent": "initiator://manual-multi-step",
		"to_agent": agent2, "payload": step2Payload,
	}, axme.RequestOptions{})
	if err != nil { log.Fatalf("create step2 failed: %v", err) }
	step2ID, _ := c2["intent_id"].(string)
	log.Printf("step 2 intent: %s — waiting...", step2ID)
	step2Status := waitForDone(ctx, client, step2ID, 60*time.Second)
	log.Printf("step 2 → %s", step2Status)

	log.Println("")
	log.Println("=== Manual Multi-Step Pipeline ===")
	log.Printf("  Step 1 (compliance): %s  id=%s", step1Status, step1ID)
	log.Printf("  Step 2 (risk):       %s  id=%s", step2Status, step2ID)
	if (step1Status == "COMPLETED" || step1Status == "IN_PROGRESS") && (step2Status == "COMPLETED" || step2Status == "IN_PROGRESS") {
		log.Println("  Result: ALL STEPS PASSED")
	} else {
		log.Println("  Result: PIPELINE FAILED")
	}
}
