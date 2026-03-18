// Access Policy Checker — human/form example (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=access-policy-checker
//	go run examples/human/form/agent.go
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
	agentAddress = envOr("AXME_AGENT_ADDRESS", "access-policy-checker")
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
func str(m map[string]any, k, d string) string { if v, ok := m[k].(string); ok { return v }; return d }

var (
	allowedAccess    = map[string]bool{"READ": true, "READ_WRITE": true}
	humanSignoff     = map[string]bool{"prod-analytics-db": true, "prod-customer-db": true, "prod-payments-db": true}
	piiBlockedAccess = map[string]bool{"READ_WRITE": true, "WRITE": true, "ADMIN": true}
)

func checkPolicy(p map[string]any) (bool, []string, []string) {
	resource := str(p, "resource", "")
	accessType := strings.ToUpper(str(p, "access_type", ""))
	requestor := str(p, "requestor", "")
	piiFields, _ := p["pii_fields"].(bool)
	var checks, violations []string

	if allowedAccess[accessType] { checks = append(checks, fmt.Sprintf("access type '%s' is in allowed set", accessType)) } else { violations = append(violations, fmt.Sprintf("access type '%s' is not allowed", accessType)) }
	if requestor != "" { checks = append(checks, fmt.Sprintf("requestor identity '%s' is present", requestor)) } else { violations = append(violations, "requestor identity is missing") }
	if piiFields && piiBlockedAccess[accessType] {
		violations = append(violations, fmt.Sprintf("resource contains PII fields; '%s' access is not permitted on PII data", accessType))
	} else if piiFields {
		checks = append(checks, fmt.Sprintf("PII data present but '%s' is read-only — acceptable", accessType))
	} else {
		checks = append(checks, "resource has no PII fields — no PII restriction applies")
	}
	_ = resource
	return len(violations) == 0, checks, violations
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	log.Printf("access-policy-checker starting  address=%s  binding=stream", agentAddress)

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

			passed, checks, violations := checkPolicy(eff)
			log.Printf("policy check for %s: passed=%v", id, passed)

			var payload map[string]any
			if passed {
				payload = map[string]any{"action": "complete", "policy_passed": true, "passed_checks": checks, "violations": []string{},
					"requires_human_signoff": humanSignoff[str(eff, "resource", "")]}
			} else {
				payload = map[string]any{"action": "fail", "policy_passed": false, "passed_checks": checks, "violations": violations}
			}
			client.ResumeIntent(ctx, id, payload, axme.RequestOptions{OwnerAgent: agentAddress})
			log.Printf("resumed %s (passed=%v)", id, passed)
		case err, ok := <-errs: if !ok { return }; log.Printf("error: %v", err)
		case <-ctx.Done(): return
		}
	}
}
