// Pre-Approval Validator — durability/reminder-escalation example (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=pre-approval-validator
//	go run examples/durability/reminder-escalation/agent.go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sort"
	"strings"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

var (
	baseURL      = envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	apiKey       = os.Getenv("AXME_API_KEY")
	agentAddress = envOr("AXME_AGENT_ADDRESS", "pre-approval-validator")
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
func str(m map[string]any, k, d string) string { if v, ok := m[k].(string); ok { return v }; return d }

var allowedTypes = map[string]bool{"config_update": true, "dependency_update": true, "rollback": true, "hotfix": true}
var validRisks = map[string]bool{"low": true, "medium": true, "high": true, "critical": true}

func sortedKeys(m map[string]bool) []string {
	keys := make([]string, 0, len(m))
	for k := range m { keys = append(keys, k) }
	sort.Strings(keys)
	return keys
}

func validateChange(p map[string]any) (bool, string) {
	changeID := str(p, "change_id", "?")
	changeType := str(p, "change_type", "")
	riskLevel := str(p, "risk_level", "")
	service := str(p, "service", "")

	if service == "" { return false, fmt.Sprintf("%s: service is required", changeID) }
	if !allowedTypes[changeType] { return false, fmt.Sprintf("%s: change_type '%s' not in %v", changeID, changeType, sortedKeys(allowedTypes)) }
	if !validRisks[riskLevel] { return false, fmt.Sprintf("%s: risk_level '%s' not in %v", changeID, riskLevel, sortedKeys(validRisks)) }
	return true, fmt.Sprintf("%s: pre-validation passed for '%s' (%s, %s risk)", changeID, service, changeType, riskLevel)
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	log.Printf("pre-approval-validator starting  address=%s  binding=stream", agentAddress)

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

			valid, reason := validateChange(eff)
			log.Printf("pre-validation for %s: valid=%v", id, valid)
			action := "complete"; if !valid { action = "fail" }
			client.ResumeIntent(ctx, id, map[string]any{"action": action, "valid": valid, "reason": reason}, axme.RequestOptions{OwnerAgent: agentAddress})
			log.Printf("resumed %s (valid=%v)", id, valid)
		case err, ok := <-errs: if !ok { return }; log.Printf("error: %v", err)
		case <-ctx.Done(): return
		}
	}
}
