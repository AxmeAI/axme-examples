// Order Processing Agent — HTTP delivery binding (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export CALLBACK_URL=https://<your-public-url>/intent
//	export PORT=8080
//	go run examples/delivery/http/agent.go
package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"os"
	"strings"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

var (
	baseURL       = envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	apiKey        = os.Getenv("AXME_API_KEY")
	agentAddress  = envOr("AXME_AGENT_ADDRESS", "http-order-processor")
	callbackURL   = os.Getenv("CALLBACK_URL")
	port          = envOr("PORT", "8080")
	webhookSecret = os.Getenv("AXME_WEBHOOK_SECRET")
)

var client *axme.Client

func envOr(k, d string) string {
	if v := os.Getenv(k); v != "" { return v }
	return d
}

func str(m map[string]any, k, d string) string {
	if v, ok := m[k].(string); ok { return v }
	return d
}

var supportedCurrencies = map[string]bool{"USD": true, "EUR": true, "GBP": true, "JPY": true}

func processOrder(p map[string]any) map[string]any {
	eventType := str(p, "event_type", "")
	orderID := str(p, "order_id", "")
	amount, _ := p["amount"].(float64)
	currency := str(p, "currency", "")

	if eventType != "order.placed" {
		return map[string]any{"action": "fail", "reason": fmt.Sprintf("unexpected event_type=%q", eventType)}
	}
	if orderID == "" {
		return map[string]any{"action": "fail", "reason": "order_id is required"}
	}
	if !supportedCurrencies[currency] {
		return map[string]any{"action": "fail", "reason": fmt.Sprintf("unsupported currency=%q", currency)}
	}
	if amount < 0.01 || amount > 1_000_000 {
		return map[string]any{"action": "fail", "reason": fmt.Sprintf("amount=%v out of range", amount)}
	}

	h := int(math.Abs(float64(hashCode(orderID)))) % 100000
	trackingID := fmt.Sprintf("TRK-%s-%05d", strings.ToUpper(orderID), h)
	return map[string]any{
		"action": "complete", "order_id": orderID, "tracking_id": trackingID,
		"status": "accepted", "currency": currency, "amount": amount,
	}
}

func hashCode(s string) int {
	h := 0
	for _, c := range s {
		h = 31*h + int(c)
	}
	return h
}

func verifySignature(body []byte, sig string) bool {
	if webhookSecret == "" { return true }
	if sig == "" { return false }
	mac := hmac.New(sha256.New, []byte(webhookSecret))
	mac.Write(body)
	expected := hex.EncodeToString(mac.Sum(nil))
	received := strings.TrimPrefix(sig, "sha256=")
	return hmac.Equal([]byte(expected), []byte(received))
}

func handleIntentAsync(intentID string) {
	ctx := context.Background()
	log.Printf("received intent %s via http callback", intentID)

	resp, err := client.GetIntent(ctx, intentID, axme.RequestOptions{})
	if err != nil { log.Printf("get_intent(%s) failed: %v", intentID, err); return }

	payload, _ := resp["payload"].(map[string]any)
	if payload == nil { payload = map[string]any{} }

	result := processOrder(payload)
	action := str(result, "action", "")

	_, err = client.ResumeIntent(ctx, intentID, result, axme.RequestOptions{OwnerAgent: agentAddress})
	if err != nil { log.Printf("resume_intent(%s) failed: %v", intentID, err); return }
	log.Printf("resumed %s  action=%s", intentID, action)
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }

	var err error
	client, err = axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	http.HandleFunc("/intent", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" { w.WriteHeader(405); return }
		body, _ := io.ReadAll(r.Body)

		if !verifySignature(body, r.Header.Get("X-Axme-Signature")) {
			w.WriteHeader(401)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"ack":true}`))

		var envelope map[string]any
		if err := json.Unmarshal(body, &envelope); err != nil { return }
		intentID := str(envelope, "intent_id", "")
		if intentID != "" {
			go handleIntentAsync(intentID)
		}
	})

	log.Printf("http-order-processor starting  address=%s  binding=http  port=%s", agentAddress, port)
	if callbackURL != "" {
		log.Printf("AXME will POST intents to: %s", callbackURL)
	}
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
