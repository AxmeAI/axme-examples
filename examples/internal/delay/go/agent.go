// Change Window Validator — internal/delay example (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=change-window-validator
//	go run examples/internal/delay/agent.go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"time"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

var (
	baseURL      = envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	apiKey       = os.Getenv("AXME_API_KEY")
	agentAddress = envOr("AXME_AGENT_ADDRESS", "change-window-validator")
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
func str(m map[string]any, k, d string) string { if v, ok := m[k].(string); ok { return v }; return d }

var (
	approvedWindows  = map[string]bool{"MW-2026-Q1-01": true, "MW-2026-Q1-02": true, "MW-2026-Q1-03": true, "MW-2026-Q1-04": true, "MW-2026-Q1-05": true, "MW-2026-Q1-06": true}
	allowedTypes     = map[string]bool{"config_update": true, "dependency_update": true, "rollback": true, "hotfix": true}
)

func validateWindow(p map[string]any) (bool, string, map[string]any) {
	changeID := str(p, "change_id", "?")
	env := str(p, "environment", "")
	changeType := str(p, "change_type", "")
	windowID := str(p, "window_id", "")
	scheduledAt := str(p, "scheduled_at", "")

	if !allowedTypes[changeType] { return false, fmt.Sprintf("%s: change_type '%s' is not allowed", changeID, changeType), nil }
	if env == "production" {
		if windowID == "" { return false, fmt.Sprintf("%s: production changes require an approved window_id", changeID), nil }
		if !approvedWindows[windowID] { return false, fmt.Sprintf("%s: window_id '%s' is not approved", changeID, windowID), nil }
	}
	if scheduledAt != "" {
		if _, err := time.Parse(time.RFC3339, scheduledAt); err != nil {
			return false, fmt.Sprintf("%s: scheduled_at '%s' is not a valid ISO timestamp", changeID, scheduledAt), nil
		}
	}
	meta := map[string]any{}
	if windowID != "" && approvedWindows[windowID] { meta["window_id"] = windowID; meta["window_approved"] = true }
	return true, fmt.Sprintf("%s: change window validated for '%s' environment", changeID, env), meta
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	log.Printf("change-window-validator starting  address=%s  binding=stream", agentAddress)

	intents, errs := client.Listen(ctx, agentAddress, axme.ListenOptions{})
	for {
		select {
		case d, ok := <-intents:
			if !ok { return }
			id := str(d, "intent_id", ""); if id == "" { continue }
			resp, _ := client.GetIntent(ctx, id, axme.RequestOptions{})
			intent, _ := resp["intent"].(map[string]any); if intent == nil { intent = resp }
			status := strings.ToUpper(str(intent, "lifecycle_status", str(intent, "status", "")))
			if !map[string]bool{"CREATED": true, "DELIVERED": true, "ACKNOWLEDGED": true, "IN_PROGRESS": true, "WAITING": true}[status] { continue }
			raw, _ := intent["payload"].(map[string]any); if raw == nil { raw = map[string]any{} }
			eff, _ := raw["parent_payload"].(map[string]any); if eff == nil { eff = raw }

			allowed, reason, meta := validateWindow(eff)
			log.Printf("window validation for %s: allowed=%v", id, allowed)
			payload := map[string]any{"action": "complete", "allowed": true, "reason": reason}
			if !allowed { payload = map[string]any{"action": "fail", "allowed": false, "reason": reason} }
			if meta != nil { for k, v := range meta { payload[k] = v } }
			client.ResumeIntent(ctx, id, payload, axme.RequestOptions{OwnerAgent: agentAddress})
			log.Printf("resumed %s (allowed=%v)", id, allowed)
		case err, ok := <-errs: if !ok { return }; log.Printf("error: %v", err)
		case <-ctx.Done(): return
		}
	}
}
