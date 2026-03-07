# Additional SDK Snippets

This directory tracks short usage snippets for SDKs that are not maintained as full runnable projects in every scenario.

Current policy:

- Full runnable examples: **Python** and **TypeScript**
- Snippet-only support: **Go**, **Java**, **.NET**
- Protocol-only examples (no cloud runtime): `../protocol/`

These snippets are shown for AXME Cloud usage and require an API key generated on the landing page.
Get API key: <https://cloud.axme.ai/alpha>

Environment model:

- `AXME_API_KEY` - required
- `AXME_BASE_URL` - optional override

## Auto-Approval Workflow Snippet

### Go

```go
resp, _ := client.CreateIntent(ctx, axme.CreateIntentRequest{
    IntentType: "intent.approval.demo.v1",
    CorrelationID: correlationID,
    FromAgent: "agent://requester",
    ToAgent: "agent://approver",
    Payload: map[string]any{"request_id": "req-123"},
})
_ = client.ResumeIntent(ctx, resp.IntentID, axme.ResumeIntentRequest{
    ApproveCurrentStep: true,
    Reason: "auto-approved by policy",
}, axme.WithOwnerAgent("agent://requester"))
_ = client.ResolveIntent(ctx, resp.IntentID, axme.ResolveIntentRequest{
    Status: "COMPLETED",
    Result: map[string]any{"approved": true, "mode": "automatic"},
})
```

### Java

```java
var created = client.createIntent(Map.of(
    "intent_type", "intent.approval.demo.v1",
    "correlation_id", correlationId,
    "from_agent", "agent://requester",
    "to_agent", "agent://approver",
    "payload", Map.of("request_id", "req-123")
), CreateIntentOptions.builder().correlationId(correlationId).build());

client.resumeIntent(created.intentId(), Map.of(
    "approve_current_step", true,
    "reason", "auto-approved by policy"
), ResolveIntentOptions.builder().ownerAgent("agent://requester").build());

client.resolveIntent(created.intentId(), Map.of(
    "status", "COMPLETED",
    "result", Map.of("approved", true, "mode", "automatic")
));
```

### .NET

```csharp
var created = await client.CreateIntentAsync(new Dictionary<string, object?>
{
    ["intent_type"] = "intent.approval.demo.v1",
    ["correlation_id"] = correlationId,
    ["from_agent"] = "agent://requester",
    ["to_agent"] = "agent://approver",
    ["payload"] = new Dictionary<string, object?> { ["request_id"] = "req-123" },
}, new CreateIntentOptions { CorrelationId = correlationId });

await client.ResumeIntentAsync(created.IntentId, new Dictionary<string, object?>
{
    ["approve_current_step"] = true,
    ["reason"] = "auto-approved by policy",
}, new ResolveIntentOptions { OwnerAgent = "agent://requester" });

await client.ResolveIntentAsync(created.IntentId, new Dictionary<string, object?>
{
    ["status"] = "COMPLETED",
    ["result"] = new Dictionary<string, object?> { ["approved"] = true, ["mode"] = "automatic" },
});
```
