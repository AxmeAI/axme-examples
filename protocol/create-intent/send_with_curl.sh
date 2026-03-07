#!/usr/bin/env bash
set -euo pipefail

: "${TARGET_URL:?Set TARGET_URL, e.g. http://localhost:8080/v1/intents}"

curl -sS -X POST "${TARGET_URL}" \
  -H "content-type: application/json" \
  --data-binary "@intent.json"
