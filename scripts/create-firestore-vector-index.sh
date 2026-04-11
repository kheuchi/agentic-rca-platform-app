#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-mon-rag-perso-2026}"
DATABASE_ID="${DATABASE_ID:-%28default%29}"
COLLECTION_GROUP="${COLLECTION_GROUP:-code-chunks}"

ACCESS_TOKEN="$(gcloud auth print-access-token)"
API_URL="https://firestore.googleapis.com/v1/projects/${PROJECT_ID}/databases/${DATABASE_ID}/collectionGroups/${COLLECTION_GROUP}/indexes"

cat > /tmp/firestore-vector-index.json <<'EOF'
{
  "queryScope": "COLLECTION",
  "fields": [
    {
      "fieldPath": "service_name",
      "order": "ASCENDING"
    },
    {
      "fieldPath": "embedding",
      "vectorConfig": {
        "dimension": 1536,
        "flat": {}
      }
    }
  ]
}
EOF

curl -sS -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  "${API_URL}" \
  -d @/tmp/firestore-vector-index.json
