"""Initiator inbox reader — inbox/reply_to delivery binding.

After running 'axme scenarios apply scenario.json --watch', the fulfillment
result is placed into the initiator's inbox. This script reads it.

The initiator side demonstrates the disconnect-safe pattern:
- Submit intent with reply_to = your inbox address
- Disconnect — you don't need to stay connected
- Come back later and read the result from inbox

Run (after scenario completes):
    export AXME_API_KEY=<initiator-api-key>
    export AXME_BASE_URL=https://api.cloud.axme.ai

    python check_inbox.py
"""
from __future__ import annotations

import json
import logging
import os
import sys

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("inbox-reader")

AXME_BASE_URL = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY  = os.environ.get("AXME_API_KEY", "")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required (initiator's key)")


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    log.info("reading inbox...")
    try:
        inbox = client.list_inbox()
    except Exception as exc:
        sys.exit(f"list_inbox() failed: {exc}")

    threads = inbox.get("threads") or []
    if not threads:
        print("\nInbox is empty. Run the scenario first:\n  axme scenarios apply scenario.json --watch\n")
        return

    print(f"\nInbox — {len(threads)} thread(s):\n")
    for t in threads:
        thread_id  = t.get("thread_id", "?")
        subject    = t.get("subject") or t.get("intent_type") or "?"
        status     = t.get("status", "?")
        updated_at = str(t.get("updated_at", ""))[:19]
        print(f"  [{status:<12}]  {subject:<40}  id={thread_id}  at={updated_at}")

    # Show latest thread details
    latest = threads[0]
    thread_id = latest.get("thread_id", "")
    if thread_id:
        print()
        try:
            detail = client.get_inbox_thread(thread_id)
        except Exception as exc:
            log.error("get_inbox_thread(%s) failed: %s", thread_id, exc)
            return

        messages = detail.get("messages") or []
        if messages:
            print(f"Latest thread {thread_id} — {len(messages)} message(s):")
            for m in messages[-3:]:  # show last 3 messages
                role    = m.get("role", "?")
                content = m.get("content") or m.get("text") or ""
                if isinstance(content, dict):
                    content = json.dumps(content, indent=2)
                print(f"\n  [{role}]")
                for line in str(content).splitlines():
                    print(f"    {line}")

    print()
    print("CLI alternatives:")
    print("  axme inbox list")
    print(f"  axme inbox get {thread_id}")
    print()


if __name__ == "__main__":
    main()
