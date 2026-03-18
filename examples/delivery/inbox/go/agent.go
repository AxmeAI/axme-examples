// Fulfillment Service Agent — inbox/reply_to delivery binding (Go).
//
// Run:
//
//	export AXME_API_KEY=<your-api-key>
//	export AXME_AGENT_ADDRESS=fulfillment-service-agent
//	go run examples/delivery/inbox/agent.go
package main

import (
	"context"
	"fmt"
	"log"
	"math"
	"os"
	"os/signal"
	"strings"

	"github.com/AxmeAI/axme-sdk-go/axme"
)

var (
	baseURL      = envOr("AXME_BASE_URL", "https://api.cloud.axme.ai")
	apiKey       = os.Getenv("AXME_API_KEY")
	agentAddress = envOr("AXME_AGENT_ADDRESS", "fulfillment-service-agent")
)

func envOr(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
func str(m map[string]any, k, d string) string { if v, ok := m[k].(string); ok { return v }; return d }

var shippingEstimates = map[string]string{
	"express": "1-2 business days", "standard": "3-5 business days", "economy": "7-10 business days",
}

func hashCode(s string) int { h := 0; for _, c := range s { h = 31*h + int(c) }; return h }

func fulfillOrder(p map[string]any) map[string]any {
	orderID := str(p, "order_id", "")
	customer := str(p, "customer_id", "")
	items, _ := p["items"].([]any)
	shipping := str(p, "shipping", "standard")

	if orderID == "" { return map[string]any{"action": "fail", "reason": "order_id is required"} }
	if len(items) == 0 { return map[string]any{"action": "fail", "reason": "items list is empty"} }
	if _, ok := shippingEstimates[shipping]; !ok {
		return map[string]any{"action": "fail", "reason": fmt.Sprintf("unknown shipping method=%q", shipping)}
	}

	totalItems := 0
	for _, it := range items {
		if m, ok := it.(map[string]any); ok {
			if q, ok := m["quantity"].(float64); ok { totalItems += int(q) }
		}
	}
	if totalItems <= 0 { return map[string]any{"action": "fail", "reason": "total item quantity must be > 0"} }

	h1 := int(math.Abs(float64(hashCode(orderID)))) % 10000
	h2 := int(math.Abs(float64(hashCode(orderID + customer)))) % 100000
	return map[string]any{
		"action": "complete",
		"fulfillment_id":  fmt.Sprintf("FUL-%05d", h2),
		"tracking_number": fmt.Sprintf("AXME-%s-%04d", strings.ToUpper(orderID), h1),
		"warehouse": "WH-US-EAST-1", "shipping_method": shipping,
		"eta": shippingEstimates[shipping], "items_shipped": totalItems, "status": "fulfilled",
	}
}

func main() {
	if apiKey == "" { log.Fatal("AXME_API_KEY is required") }
	client, err := axme.NewClient(axme.ClientConfig{APIKey: apiKey, BaseURL: baseURL})
	if err != nil { log.Fatalf("client init: %v", err) }

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()

	log.Printf("fulfillment-service-agent starting  address=%s  binding=stream", agentAddress)

	intents, errs := client.Listen(ctx, agentAddress, axme.ListenOptions{})
	for {
		select {
		case delivery, ok := <-intents:
			if !ok { return }
			id := str(delivery, "intent_id", "")
			if id == "" { continue }
			log.Printf("received order intent %s", id)

			resp, err := client.GetIntent(ctx, id, axme.RequestOptions{})
			if err != nil { log.Printf("get_intent(%s) failed: %v", id, err); continue }
			payload, _ := resp["payload"].(map[string]any)
			if payload == nil { payload = map[string]any{} }

			result := fulfillOrder(payload)
			_, err = client.ResumeIntent(ctx, id, result, axme.RequestOptions{OwnerAgent: agentAddress})
			if err != nil { log.Printf("resume_intent(%s) failed: %v", id, err); continue }
			log.Printf("resumed %s  action=%s", id, str(result, "action", ""))
		case err, ok := <-errs:
			if !ok { return }
			log.Printf("stream error: %v", err)
		case <-ctx.Done():
			log.Println("shutting down"); return
		}
	}
}
