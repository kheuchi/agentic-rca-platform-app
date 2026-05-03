#!/usr/bin/env bash
set -euo pipefail

namespace="${1:-rag-dev}"
question="${2:-Why is frontendproxy failing to route requests?}"
service="${3:-frontendproxy}"
time_range="${4:-1h}"

pub="$(kubectl get secret -n "$namespace" langfuse-secrets -o jsonpath='{.data.public-key}' | base64 -d)"
sec="$(kubectl get secret -n "$namespace" langfuse-secrets -o jsonpath='{.data.secret-key}' | base64 -d)"
auth="$(printf '%s:%s' "$pub" "$sec" | base64 -w0)"

langfuse_pf_log="$(mktemp)"
backend_pf_log="$(mktemp)"

kubectl port-forward -n "$namespace" svc/langfuse-web 3000:3000 >"$langfuse_pf_log" 2>&1 &
pf_langfuse=$!
kubectl port-forward -n "$namespace" svc/rag-backend 18080:80 >"$backend_pf_log" 2>&1 &
pf_backend=$!

cleanup() {
  kill "$pf_langfuse" "$pf_backend" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:3000/api/public/health >/dev/null 2>&1 \
    && curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

printf 'HEALTH_LF='
curl -fsS http://127.0.0.1:3000/api/public/health
printf '\nHEALTH_BE='
curl -fsS http://127.0.0.1:18080/health
printf '\nTRACES_BEFORE='
curl -fsS -H "Authorization: Basic $auth" "http://127.0.0.1:3000/api/public/traces?limit=3"
printf '\nRCA_RESPONSE='
curl -fsS -X POST http://127.0.0.1:18080/query/rca \
  -H 'Content-Type: application/json' \
  -d "{\"question\":\"$question\",\"service\":\"$service\",\"time_range\":\"$time_range\",\"stream\":false}"
printf '\n'

sleep 12

printf 'TRACES_AFTER='
curl -fsS -H "Authorization: Basic $auth" "http://127.0.0.1:3000/api/public/traces?limit=5"
printf '\nOBS_AFTER='
curl -fsS -H "Authorization: Basic $auth" "http://127.0.0.1:3000/api/public/observations?limit=10"
printf '\nSESSIONS_AFTER='
curl -fsS -H "Authorization: Basic $auth" "http://127.0.0.1:3000/api/public/sessions?limit=10"
printf '\nBACKEND_LOGS_TAIL\n'
kubectl logs -n "$namespace" deploy/rag-backend --tail=120
