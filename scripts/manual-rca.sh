#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

curl -s -X POST "${BASE_URL}/query/rca" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What could cause high latency in the checkout service?",
    "service": "checkoutservice",
    "time_range": "1h",
    "stream": false
  }' \
  --max-time 120
