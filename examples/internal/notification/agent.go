// Risk Assessment Agent — internal/notification example (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=risk-assessment-agent
//	go run examples/internal/notification/agent.go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strconv"
	"strings"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

var (
	baseURL      = envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	apiKey       = os.Getenv("AXME_API_KEY")
	agentAddress = envOr("AXME_AGENT_ADDRESS", "risk-assessment-agent")
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
func str(m map[string]any, k, d string) string { if v, ok := m[k].(string); ok { return v }; return d }

func assessRisk(p map[string]any) (int, string, []string) {
	version := str(p, "version", "0.0.0")
	env := str(p, "environment", "")
	changeCount := toInt(p["change_count"])
	threshold := toInt(p["risk_threshold"])
	if threshold == 0 { threshold = 30 }

	parts := strings.SplitN(version, ".", 3)
	major, _ := strconv.Atoi(parts[0])
	minor := 0; if len(parts) > 1 { minor, _ = strconv.Atoi(parts[1]) }

	score := 0
	var factors []string
	if major >= 4 { score += 40; factors = append(factors, fmt.Sprintf("major version bump (v%d.x) +40", major)) } else if minor >= 5 { score += 15; factors = append(factors, "significant minor version bump +15") }
	if changeCount > 30 { score += 30; factors = append(factors, fmt.Sprintf("high change count (%d changes) +30", changeCount)) }
	if env == "production" { score += 25; factors = append(factors, "production environment +25") } else if env == "staging" || env == "canary" { score += 10; factors = append(factors, "staging environment +10") }

	level := "LOW"
	if score >= threshold { level = "HIGH" } else if score >= threshold/2 { level = "MEDIUM" }
	return score, level, factors
}

func toInt(v any) int {
	switch n := v.(type) {
	case float64: return int(n)
	case int: return n
	case string: i, _ := strconv.Atoi(n); return i
	}
	return 0
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	log.Printf("risk-assessment-agent starting  address=%s  binding=stream", agentAddress)

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

			score, level, factors := assessRisk(eff)
			log.Printf("risk assessment for %s: score=%d level=%s", id, score, level)
			client.ResumeIntent(ctx, id, map[string]any{"action": "complete", "risk_score": score, "risk_level": level, "factors": factors}, axme.RequestOptions{OwnerAgent: agentAddress})
			log.Printf("resumed %s (risk=%s)", id, level)
		case err, ok := <-errs: if !ok { return }; log.Printf("error: %v", err)
		case <-ctx.Done(): return
		}
	}
}
