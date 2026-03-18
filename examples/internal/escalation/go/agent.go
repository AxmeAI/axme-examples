// Incident Classifier Agent — internal/escalation example (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=incident-classifier-agent
//	go run examples/internal/escalation/agent.go
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
	agentAddress = envOr("AXME_AGENT_ADDRESS", "incident-classifier-agent")
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
func str(m map[string]any, k, d string) string { if v, ok := m[k].(string); ok { return v }; return d }

var severitySLA = map[string]int{"P1": 5, "P2": 15, "P3": 60, "P4": 240}
var criticalServices = map[string]bool{"api-gateway": true, "auth-service": true, "payments-processor": true}

func classifyIncident(p map[string]any) map[string]any {
	incidentID := str(p, "incident_id", "?")
	severity := str(p, "severity", "P3")
	service := str(p, "service", "")
	symptom := str(p, "symptom", "")
	sla := severitySLA[severity]; if sla == 0 { sla = 60 }
	isCritical := criticalServices[service]

	affected := []string{}
	if service != "" { affected = append(affected, service) }
	if isCritical { affected = append(affected, "downstream-dependents") }

	escalation := "on-call"
	if (severity == "P1" || severity == "P2") && isCritical { escalation = "on-call → team-lead → engineering-director" } else if severity == "P1" || severity == "P2" { escalation = "on-call → team-lead" }

	hasErrorRate := strings.Contains(strings.ToLower(symptom), "error rate") || strings.Contains(strings.ToLower(symptom), "5xx")

	return map[string]any{
		"incident_id": incidentID, "severity": severity, "is_critical_service": isCritical,
		"has_error_rate_signal": hasErrorRate, "affected_components": affected,
		"sla_minutes": sla, "escalation_path": escalation,
		"classification_note": fmt.Sprintf("%s: %s on '%s' — SLA=%dm, escalation: %s", incidentID, severity, service, sla, escalation),
	}
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	log.Printf("incident-classifier starting  address=%s  binding=stream", agentAddress)

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

			result := classifyIncident(eff)
			log.Printf("classified %s: %s", id, result["classification_note"])
			result["action"] = "complete"
			client.ResumeIntent(ctx, id, result, axme.RequestOptions{OwnerAgent: agentAddress})
			log.Printf("resumed %s", id)
		case err, ok := <-errs: if !ok { return }; log.Printf("error: %v", err)
		case <-ctx.Done(): return
		}
	}
}
