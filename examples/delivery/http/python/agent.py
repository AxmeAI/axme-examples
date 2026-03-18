"""Order Processing Agent — HTTP delivery binding.

Delivery: http  (AXME POSTs intent to callback_url)
AXME delivers intents by making an HTTP POST to the agent's registered callback_url.
The agent runs an HTTP server that accepts these deliveries.

This pattern is suitable for:
- Enterprise systems that already expose HTTP endpoints
- Microservices behind a public URL (Cloud Run, AWS Lambda, etc.)
- Webhook-style integrations
- When you want AXME to push rather than agents pulling

The agent registers itself with delivery_mode=http and a callback_url.
AXME will POST to that URL with retry and dead-letter tracking.

Security: AXME signs every delivery request with HMAC-SHA256.
Verify the signature using AXME_WEBHOOK_SECRET (see below).

Run:
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/http-order-processor
    export AXME_BASE_URL=https://api.cloud.axme.ai
    export CALLBACK_URL=https://<your-public-url>/intent    # public URL AXME will POST to
    export PORT=8080                                          # local listen port

    python agent.py

Then in another terminal:
    axme scenarios apply examples/delivery/http/scenario.json --watch

Note: callback_url must be publicly reachable by AXME.
For local development, use ngrok: ngrok http 8080
Then set CALLBACK_URL=https://<ngrok-id>.ngrok.io/intent
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("http-order-processor")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AXME_BASE_URL       = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY        = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS  = os.environ.get("AXME_AGENT_ADDRESS", "http-order-processor")
CALLBACK_URL        = os.environ.get("CALLBACK_URL", "")
PORT                = int(os.environ.get("PORT", "8080"))
AXME_WEBHOOK_SECRET = os.environ.get("AXME_WEBHOOK_SECRET", "")  # optional HMAC verification

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

# ---------------------------------------------------------------------------
# Business logic — order processing, no stubs
# ---------------------------------------------------------------------------

_SUPPORTED_CURRENCIES  = {"USD", "EUR", "GBP", "JPY"}
_MIN_ORDER_AMOUNT      = 0.01
_MAX_ORDER_AMOUNT      = 1_000_000.00


def _process_order(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and process an order placement event."""
    event_type = payload.get("event_type", "")
    order_id   = payload.get("order_id", "")
    amount     = payload.get("amount", 0)
    currency   = payload.get("currency", "")

    if event_type != "order.placed":
        return {"action": "fail", "reason": f"unexpected event_type={event_type!r}"}

    if not order_id:
        return {"action": "fail", "reason": "order_id is required"}

    if currency not in _SUPPORTED_CURRENCIES:
        return {
            "action": "fail",
            "reason": f"unsupported currency={currency!r}  supported: {sorted(_SUPPORTED_CURRENCIES)}",
        }

    if not (_MIN_ORDER_AMOUNT <= amount <= _MAX_ORDER_AMOUNT):
        return {
            "action": "fail",
            "reason": f"amount={amount} is out of range [{_MIN_ORDER_AMOUNT}, {_MAX_ORDER_AMOUNT}]",
        }

    # Generate tracking ID (in production: call payment/fulfillment service)
    tracking_id = f"TRK-{order_id.upper()}-{abs(hash(order_id)) % 100000:05d}"

    return {
        "action":      "complete",
        "order_id":    order_id,
        "tracking_id": tracking_id,
        "status":      "accepted",
        "currency":    currency,
        "amount":      amount,
    }


# ---------------------------------------------------------------------------
# HMAC signature verification (optional, recommended in production)
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, signature_header: str) -> bool:
    """Verify AXME HMAC-SHA256 delivery signature.  Returns True if valid or no secret configured."""
    if not AXME_WEBHOOK_SECRET:
        return True  # verification disabled — configure AXME_WEBHOOK_SECRET in production

    if not signature_header:
        log.warning("missing X-Axme-Signature header — rejecting delivery")
        return False

    expected = hmac.new(
        AXME_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")

    return hmac.compare_digest(expected, received)


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

_client: AxmeClient | None = None


class _IntentHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        log.debug(fmt, *args)  # suppress default access log, route through our logger

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/intent":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        body   = self.rfile.read(length)

        # Verify signature before processing
        sig = self.headers.get("X-Axme-Signature", "")
        if not _verify_signature(body, sig):
            log.warning("signature verification failed — returning 401")
            self.send_response(401)
            self.end_headers()
            return

        # Respond 200 immediately (AXME expects fast ACK)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ack":true}')

        # Process in background thread so we don't block AXME's delivery connection
        try:
            envelope  = json.loads(body)
            intent_id = envelope.get("intent_id")
            if intent_id:
                threading.Thread(
                    target=_handle_intent_async,
                    args=(intent_id,),
                    daemon=True,
                ).start()
            else:
                log.warning("received POST without intent_id: %s", envelope)
        except Exception as exc:
            log.error("failed to parse delivery body: %s", exc)


def _handle_intent_async(intent_id: str) -> None:
    """Called in background thread after ACK is sent to AXME."""
    assert _client is not None
    log.info("received intent %s via http callback", intent_id)

    try:
        intent = _client.get_intent(intent_id)
    except Exception as exc:
        log.error("get_intent(%s) failed: %s", intent_id, exc)
        return

    payload = intent.get("payload") or {}
    result  = _process_order(payload)
    action  = result.pop("action")

    try:
        _client.resume_intent(
            intent_id,
            {"action": action, **result},
            owner_agent=AXME_AGENT_ADDRESS,
        )
        log.info("resumed %s  action=%s", intent_id, action)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    global _client
    _client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    if not CALLBACK_URL:
        log.warning(
            "CALLBACK_URL not set. For local dev, start ngrok: ngrok http %d  "
            "then set CALLBACK_URL=https://<id>.ngrok.io/intent",
            PORT,
        )

    server = HTTPServer(("0.0.0.0", PORT), _IntentHandler)
    log.info(
        "http-order-processor starting  address=%s  binding=http  port=%d",
        AXME_AGENT_ADDRESS,
        PORT,
    )
    log.info("AXME will POST intents to: %s", CALLBACK_URL or f"http://localhost:{PORT}/intent")
    log.info("health check: http://localhost:%d/health", PORT)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
