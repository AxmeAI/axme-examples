// Batch Processor Agent — poll delivery binding (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=batch-processor-agent
//	go run examples/delivery/poll/agent.go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"time"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

var (
	baseURL      = envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	apiKey       = os.Getenv("AXME_API_KEY")
	agentAddress = envOr("AXME_AGENT_ADDRESS", "batch-processor-agent")
	pollInterval = parseDuration(envOr("POLL_INTERVAL", "10"))
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
func str(m map[string]any, k, d string) string { if v, ok := m[k].(string); ok { return v }; return d }

func parseDuration(s string) time.Duration {
	n, _ := strconv.Atoi(s)
	if n <= 0 { n = 10 }
	return time.Duration(n) * time.Second
}

var supportedTypes = map[string]int{
	"transactions": 14203, "invoices": 1847, "orders": 3291, "events": 82014,
}

func processBatch(p map[string]any) map[string]any {
	batchID := str(p, "batch_id", "?")
	recordType := str(p, "record_type", "")
	dateRange := str(p, "date_range", "")
	if batchID == "" || batchID == "?" { return map[string]any{"action": "fail", "reason": "batch_id is required"} }
	if _, ok := supportedTypes[recordType]; !ok {
		return map[string]any{"action": "fail", "reason": fmt.Sprintf("unsupported record_type=%q", recordType)}
	}
	if dateRange == "" { return map[string]any{"action": "fail", "reason": "date_range is required"} }
	return map[string]any{
		"action": "complete", "batch_id": batchID, "record_type": recordType,
		"date_range": dateRange, "record_count": supportedTypes[recordType], "status": "processed",
	}
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()

	log.Printf("batch-processor-agent starting  address=%s  binding=poll  interval=%s", agentAddress, pollInterval)
	seen := map[string]bool{}

	for {
		select {
		case <-ctx.Done():
			log.Println("shutting down")
			return
		default:
		}

		pollCtx, pollCancel := context.WithTimeout(ctx, 5*time.Second)
		intents, errs := client.Listen(pollCtx, agentAddress, axme.ListenOptions{WaitSeconds: 2})
		newCount := 0
	drain:
		for {
			select {
			case delivery, ok := <-intents:
				if !ok { break drain }
				id := str(delivery, "intent_id", "")
				if id == "" || seen[id] { continue }
				seen[id] = true
				log.Printf("processing intent %s", id)

				resp, err := client.GetIntent(ctx, id, axme.RequestOptions{})
				if err != nil { log.Printf("get_intent(%s) failed: %v", id, err); continue }
				payload, _ := resp["payload"].(map[string]any)
				if payload == nil { payload = map[string]any{} }

				result := processBatch(payload)
				action := result["action"]
				delete(result, "action")
				result["action"] = action

				_, err = client.ResumeIntent(ctx, id, result, axme.RequestOptions{OwnerAgent: agentAddress})
				if err != nil { log.Printf("resume_intent(%s) failed: %v", id, err); continue }
				log.Printf("resumed %s  action=%s", id, action)
				newCount++
			case err, ok := <-errs:
				if !ok { break drain }
				if !strings.Contains(err.Error(), "context") { log.Printf("poll error: %v", err) }
				break drain
			}
		}
		pollCancel()
		if newCount > 0 { log.Printf("poll cycle done  processed=%d", newCount) }
		time.Sleep(pollInterval)
	}
}
