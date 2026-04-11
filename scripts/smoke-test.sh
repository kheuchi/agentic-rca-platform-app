#!/usr/bin/env bash
# Phase 4.5d - End-to-end smoke test
# Usage: wsl bash scripts/smoke-test.sh
#
# Prerequisites:
#   kubectl port-forward svc/rag-backend 8000:8000 -n rag-dev
#
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
REPO_URL="${REPO_URL:-https://github.com/open-telemetry/opentelemetry-demo}"
BRANCH="${BRANCH:-main}"
TIMEOUT="${TIMEOUT:-300}"
QUERY_POLL_TIMEOUT="${QUERY_POLL_TIMEOUT:-600}"

BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[1;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

json_get() {
  local payload="$1"
  local field="$2"
  printf '%s' "$payload" | python3 -c "import json, sys; data=json.load(sys.stdin); value=data.get(sys.argv[1], ''); print(value if value is not None else '')" "$field" 2>/dev/null || true
}

info "Step 0: Health check"
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/health")
if [ "$HTTP_CODE" != "200" ]; then
  fail "Backend not reachable (HTTP $HTTP_CODE). Is port-forward running?"
  exit 1
fi
ok "Backend healthy"

info "Step 1: Triggering repo ingest - ${REPO_URL} (branch: ${BRANCH})"
INGEST_RESP=$(curl -s -X POST "${BASE_URL}/ingest/repo" \
  -H "Content-Type: application/json" \
  -d "{
    \"repo_url\": \"${REPO_URL}\",
    \"branch\": \"${BRANCH}\",
    \"services\": [\"checkoutservice\"],
    \"file_patterns\": [\"**/*.go\"]
  }")

JOB_ID=$(printf '%s' "$INGEST_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('job_id', ''))" 2>/dev/null || true)
if [ -z "$JOB_ID" ]; then
  fail "Could not extract job_id from response: ${INGEST_RESP}"
  exit 1
fi
ok "Job queued: ${JOB_ID}"

info "Step 2: Polling job status (timeout: ${TIMEOUT}s)"
ELAPSED=0
INTERVAL=10
STATUS_TRACKING_AVAILABLE=true
CHUNKS=0
STATUS="unknown"

while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
  STATUS_FILE=$(mktemp)
  HTTP_CODE=$(curl -s -o "$STATUS_FILE" -w '%{http_code}' "${BASE_URL}/ingest/status/${JOB_ID}")
  STATUS_RESP=$(cat "$STATUS_FILE")
  rm -f "$STATUS_FILE"

  if [ "$HTTP_CODE" != "200" ]; then
    STATUS_TRACKING_AVAILABLE=false
    warn "Status endpoint unavailable (HTTP ${HTTP_CODE}) - continuing with query-based polling"
    break
  fi

  STATUS=$(json_get "$STATUS_RESP" "status")
  PROGRESS=$(json_get "$STATUS_RESP" "progress")
  CHUNKS=$(json_get "$STATUS_RESP" "chunks_indexed")
  ERROR_MSG=$(json_get "$STATUS_RESP" "error")

  info "  status=${STATUS} progress=${PROGRESS} chunks=${CHUNKS} (${ELAPSED}s elapsed)"

  if [ "$STATUS" = "completed" ]; then
    ok "Ingest completed - ${CHUNKS} chunks indexed"
    break
  fi

  if [ "$STATUS" = "failed" ]; then
    fail "Ingest failed: ${ERROR_MSG}"
    exit 1
  fi

  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done

if [ "$STATUS_TRACKING_AVAILABLE" = true ] && [ "$STATUS" != "completed" ]; then
  fail "Timeout after ${TIMEOUT}s (last status: ${STATUS})"
  exit 1
fi

info "Step 3: Querying indexed code"
QUERY_ELAPSED=0
QUERY_INTERVAL=15
COUNT=0
QUERY_RESP=""

while [ "$QUERY_ELAPSED" -lt "$QUERY_POLL_TIMEOUT" ]; do
  QUERY_RESP=$(curl -s -X POST "${BASE_URL}/query" \
    -H "Content-Type: application/json" \
    -d '{
      "query": "checkout service main function",
      "top_k": 3,
      "service_filter": "checkoutservice"
    }')

  COUNT=$(printf '%s' "$QUERY_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")

  if [ "${COUNT:-0}" -gt 0 ]; then
    ok "Query returned ${COUNT} results"
    break
  fi

  info "  no results yet (${QUERY_ELAPSED}s elapsed) - waiting for indexing"
  sleep "$QUERY_INTERVAL"
  QUERY_ELAPSED=$((QUERY_ELAPSED + QUERY_INTERVAL))
done

if [ "${COUNT:-0}" -le 0 ]; then
  fail "Query returned 0 results after ${QUERY_POLL_TIMEOUT}s - Firestore vector search may not be working"
  echo "  Response: ${QUERY_RESP}"
  exit 1
fi

info "Step 4: Running RCA agent query"
RCA_RESP=$(curl -s -X POST "${BASE_URL}/query/rca" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What could cause high latency in the checkout service?",
    "service": "checkoutservice",
    "time_range": "1h",
    "stream": false
  }' --max-time 120)

ROOT_CAUSE=$(printf '%s' "$RCA_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('root_cause', '')[:100])" 2>/dev/null || echo "")
CONFIDENCE=$(printf '%s' "$RCA_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('confidence', 0))" 2>/dev/null || echo "0")

if [ -n "$ROOT_CAUSE" ]; then
  ok "RCA agent returned result (confidence: ${CONFIDENCE})"
  echo "  Root cause: ${ROOT_CAUSE}..."
else
  warn "RCA agent returned empty result (may be expected if OTel Demo has no recent data)"
  echo "  Response: ${RCA_RESP:0:200}"
fi

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Phase 4.5d smoke test PASSED${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "  Job ID:         ${JOB_ID}"
echo "  Chunks indexed: ${CHUNKS}"
echo "  Query results:  ${COUNT}"
echo "  RCA confidence: ${CONFIDENCE}"
echo ""
