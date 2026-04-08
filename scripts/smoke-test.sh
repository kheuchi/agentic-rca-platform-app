#!/usr/bin/env bash
# Phase 4.5d — End-to-end smoke test
# Usage: wsl bash scripts/smoke-test.sh
#
# Prerequisites:
#   kubectl port-forward svc/rag-backend 8000:8000 -n rag-dev
#
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
REPO_URL="${REPO_URL:-https://github.com/open-telemetry/opentelemetry-demo}"
BRANCH="${BRANCH:-main}"
TIMEOUT="${TIMEOUT:-300}"  # 5 minutes max

BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[1;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

# -----------------------------------------------------------
# Step 0 — Health check
# -----------------------------------------------------------
info "Step 0: Health check"
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/health")
if [ "$HTTP_CODE" != "200" ]; then
  fail "Backend not reachable (HTTP $HTTP_CODE). Is port-forward running?"
  exit 1
fi
ok "Backend healthy"

# -----------------------------------------------------------
# Step 1 — Trigger repo ingest
# -----------------------------------------------------------
info "Step 1: Triggering repo ingest — ${REPO_URL} (branch: ${BRANCH})"
INGEST_RESP=$(curl -s -X POST "${BASE_URL}/ingest/repo" \
  -H "Content-Type: application/json" \
  -d "{
    \"repo_url\": \"${REPO_URL}\",
    \"branch\": \"${BRANCH}\",
    \"services\": [\"checkoutservice\"],
    \"file_patterns\": [\"**/*.go\"]
  }")

JOB_ID=$(echo "$INGEST_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null || true)
if [ -z "$JOB_ID" ]; then
  fail "Could not extract job_id from response: ${INGEST_RESP}"
  exit 1
fi
ok "Job queued: ${JOB_ID}"

# -----------------------------------------------------------
# Step 2 — Poll job status until completed or timeout
# -----------------------------------------------------------
info "Step 2: Polling job status (timeout: ${TIMEOUT}s)..."
ELAPSED=0
INTERVAL=10

while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
  STATUS_RESP=$(curl -s "${BASE_URL}/ingest/status/${JOB_ID}")
  STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
  PROGRESS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('progress',0))" 2>/dev/null || echo "0")
  CHUNKS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('chunks_indexed',0))" 2>/dev/null || echo "0")
  ERROR=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','') or '')" 2>/dev/null || echo "")

  info "  status=${STATUS}  progress=${PROGRESS}  chunks=${CHUNKS}  (${ELAPSED}s elapsed)"

  if [ "$STATUS" = "completed" ]; then
    ok "Ingest completed — ${CHUNKS} chunks indexed"
    break
  fi

  if [ "$STATUS" = "failed" ]; then
    fail "Ingest failed: ${ERROR}"
    exit 1
  fi

  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done

if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
  fail "Timeout after ${TIMEOUT}s (last status: ${STATUS})"
  exit 1
fi

# -----------------------------------------------------------
# Step 3 — Query the indexed code
# -----------------------------------------------------------
info "Step 3: Querying indexed code..."
QUERY_RESP=$(curl -s -X POST "${BASE_URL}/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "checkout service main function",
    "top_k": 3,
    "service_filter": "checkoutservice"
  }')

COUNT=$(echo "$QUERY_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo "0")

if [ "$COUNT" -gt 0 ]; then
  ok "Query returned ${COUNT} results"
  echo "$QUERY_RESP" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for i, r in enumerate(data.get('results', [])[:3]):
    print(f\"  [{i+1}] {r.get('file_path','')} (score: {r.get('score',0):.4f})\")
    content = r.get('content','')[:100].replace(chr(10),' ')
    print(f\"      {content}...\")
" 2>/dev/null || true
else
  fail "Query returned 0 results — Firestore vector search may not be working"
  echo "  Response: ${QUERY_RESP}"
  exit 1
fi

# -----------------------------------------------------------
# Step 4 — RCA agent query (sync mode)
# -----------------------------------------------------------
info "Step 4: Running RCA agent query..."
RCA_RESP=$(curl -s -X POST "${BASE_URL}/query/rca" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What could cause high latency in the checkout service?",
    "service": "checkoutservice",
    "time_range": "1h",
    "stream": false
  }' --max-time 120)

ROOT_CAUSE=$(echo "$RCA_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('root_cause','')[:100])" 2>/dev/null || echo "")
CONFIDENCE=$(echo "$RCA_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('confidence',0))" 2>/dev/null || echo "0")

if [ -n "$ROOT_CAUSE" ] && [ "$ROOT_CAUSE" != "" ]; then
  ok "RCA agent returned result (confidence: ${CONFIDENCE})"
  echo "  Root cause: ${ROOT_CAUSE}..."
else
  warn "RCA agent returned empty result (may be expected if OTel Demo has no recent data)"
  echo "  Response: ${RCA_RESP:0:200}"
fi

# -----------------------------------------------------------
# Summary
# -----------------------------------------------------------
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
