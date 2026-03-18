// Budget Envelope Validator — human/email example (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=budget-envelope-validator
//	go run examples/human/email/agent.go
package main

import (
	"context"
	"fmt"
	"log"
	"math"
	"os"
	"os/signal"
	"sort"
	"strings"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

var (
	baseURL      = envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	apiKey       = os.Getenv("AXME_API_KEY")
	agentAddress = envOr("AXME_AGENT_ADDRESS", "budget-envelope-validator")
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
func str(m map[string]any, k, d string) string { if v, ok := m[k].(string); ok { return v }; return d }

var envelopes = map[string]float64{
	"cloud_infrastructure": 50000, "software_licenses": 20000,
	"contractor_services": 40000, "hardware": 15000,
}

func validateBudget(p map[string]any) (bool, string, map[string]any) {
	budgetID := str(p, "budget_id", "?")
	amount, _ := p["amount"].(float64)
	currency := str(p, "currency", "USD")
	category := str(p, "category", "")

	envelope, ok := envelopes[category]
	if !ok {
		keys := make([]string, 0, len(envelopes))
		for k := range envelopes { keys = append(keys, k) }
		sort.Strings(keys)
		return false, fmt.Sprintf("%s: unknown category %q; known: %v", budgetID, category, keys), nil
	}
	if amount > envelope {
		return false, fmt.Sprintf("%s: %s %.0f exceeds quarterly envelope of %s %.0f for %q", budgetID, currency, amount, currency, envelope, category),
			map[string]any{"envelope": envelope, "overage": amount - envelope}
	}
	headroom := math.Round((envelope-amount)/envelope*1000) / 10
	return true, fmt.Sprintf("%s: %s %.0f is within %q envelope (%.1f%% headroom)", budgetID, currency, amount, category, headroom),
		map[string]any{"envelope": envelope, "headroom_pct": headroom}
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	log.Printf("budget-envelope-validator starting  address=%s  binding=stream", agentAddress)

	intents, errs := client.Listen(ctx, agentAddress, axme.ListenOptions{})
	for {
		select {
		case d, ok := <-intents:
			if !ok { return }
			id := str(d, "intent_id", ""); if id == "" { continue }
			log.Printf("received intent %s", id)

			resp, _ := client.GetIntent(ctx, id, axme.RequestOptions{})
			intent, _ := resp["intent"].(map[string]any); if intent == nil { intent = resp }
			status := strings.ToUpper(str(intent, "lifecycle_status", str(intent, "status", "")))
			if !map[string]bool{"CREATED": true, "DELIVERED": true, "ACKNOWLEDGED": true, "IN_PROGRESS": true, "WAITING": true}[status] { continue }

			raw, _ := intent["payload"].(map[string]any); if raw == nil { raw = map[string]any{} }
			eff, _ := raw["parent_payload"].(map[string]any); if eff == nil { eff = raw }

			ok2, reason, meta := validateBudget(eff)
			log.Printf("budget validation for %s: ok=%v", id, ok2)

			var payload map[string]any
			if ok2 {
				payload = map[string]any{"action": "complete", "within_envelope": true, "reason": reason}
				if meta != nil { for k, v := range meta { payload[k] = v } }
			} else {
				payload = map[string]any{"action": "fail", "within_envelope": false, "reason": reason}
			}
			client.ResumeIntent(ctx, id, payload, axme.RequestOptions{OwnerAgent: agentAddress})
			log.Printf("resumed %s (within_envelope=%v)", id, ok2)
		case err, ok := <-errs: if !ok { return }; log.Printf("error: %v", err)
		case <-ctx.Done(): return
		}
	}
}
