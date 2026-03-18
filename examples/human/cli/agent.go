// Deploy Readiness Checker — human/cli example (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=deploy-readiness-checker
//	go run examples/human/cli/agent.go
package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"regexp"
	"strings"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

var (
	baseURL      = envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	apiKey       = os.Getenv("AXME_API_KEY")
	agentAddress = envOr("AXME_AGENT_ADDRESS", "deploy-readiness-checker")
	semverRe     = regexp.MustCompile(`^\d+\.\d+\.\d+$`)
	allowedEnvs  = map[string]bool{"staging": true, "canary": true, "preview": true}
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
func str(m map[string]any, k, d string) string { if v, ok := m[k].(string); ok { return v }; return d }

func checkReadiness(p map[string]any) (bool, []string, []string) {
	version := str(p, "version", "")
	env := str(p, "environment", "")
	rollback := str(p, "rollback_tag", "")
	service := str(p, "service", "")
	var passed, failures []string

	if semverRe.MatchString(version) { passed = append(passed, "version '"+version+"' is valid semver") } else { failures = append(failures, "version '"+version+"' is not valid semver") }
	if allowedEnvs[env] { passed = append(passed, "environment '"+env+"' is in allowed list") } else { failures = append(failures, "environment '"+env+"' not in allowed set") }
	if rollback != "" { passed = append(passed, "rollback_tag '"+rollback+"' is set") } else { failures = append(failures, "rollback_tag is missing") }
	if service != "" { passed = append(passed, "service '"+service+"' is identified") } else { failures = append(failures, "service name is empty") }

	return len(failures) == 0, passed, failures
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	log.Printf("deploy-readiness-checker starting  address=%s  binding=stream", agentAddress)

	intents, errs := client.Listen(ctx, agentAddress, axme.ListenOptions{})
	for {
		select {
		case d, ok := <-intents:
			if !ok { return }
			id := str(d, "intent_id", ""); if id == "" { continue }
			log.Printf("received intent %s", id)

			resp, err := client.GetIntent(ctx, id, axme.RequestOptions{})
			if err != nil { log.Printf("get_intent(%s) failed: %v", id, err); continue }
			intent, _ := resp["intent"].(map[string]any); if intent == nil { intent = resp }
			status := strings.ToUpper(str(intent, "lifecycle_status", str(intent, "status", "")))
			if !map[string]bool{"CREATED": true, "DELIVERED": true, "ACKNOWLEDGED": true, "IN_PROGRESS": true, "WAITING": true}[status] { continue }

			raw, _ := intent["payload"].(map[string]any); if raw == nil { raw = map[string]any{} }
			eff, _ := raw["parent_payload"].(map[string]any); if eff == nil { eff = raw }

			ready, passed, failures := checkReadiness(eff)
			log.Printf("readiness for %s: ready=%v passed=%d failed=%d", id, ready, len(passed), len(failures))

			var payload map[string]any
			if ready { payload = map[string]any{"action": "complete", "ready": true, "passed_checks": passed, "failures": []string{}} } else { payload = map[string]any{"action": "fail", "ready": false, "passed_checks": passed, "failures": failures} }
			if _, err = client.ResumeIntent(ctx, id, payload, axme.RequestOptions{OwnerAgent: agentAddress}); err != nil { log.Printf("resume failed: %v", err) }
			log.Printf("resumed %s (ready=%v)", id, ready)
		case err, ok := <-errs: if !ok { return }; log.Printf("error: %v", err)
		case <-ctx.Done(): return
		}
	}
}
