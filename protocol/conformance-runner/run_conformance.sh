#!/usr/bin/env bash
set -euo pipefail

: "${TARGET_BASE_URL:?Set TARGET_BASE_URL for your implementation endpoint}"

echo "Run axme-conformance against: ${TARGET_BASE_URL}"
echo "Example:"
echo "  git clone https://github.com/AxmeAI/axme-conformance.git"
echo "  cd axme-conformance"
echo "  TARGET_BASE_URL=${TARGET_BASE_URL} make test"
