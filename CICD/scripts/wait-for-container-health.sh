#!/bin/sh
# Wait until a Docker container is running and passes its health endpoint.
# Usage: wait-for-container-health.sh <container_name> [max_attempts] [interval_sec] [health_url]
#
# Designed to run on the deployment host (invoked from Jenkins via ssh bash -s).
set -eu

CONTAINER="${1:?container name is required}"
MAX_ATTEMPTS="${2:-36}"
INTERVAL="${3:-5}"
HEALTH_URL="${4:-http://127.0.0.1:8000/health}"
# api = JSON body status healthy (backend); http = HTTP 200 only (frontend/nginx)
MODE="${5:-api}"

echo "==> Waiting for '${CONTAINER}' (url=${HEALTH_URL}, attempts=${MAX_ATTEMPTS}, interval=${INTERVAL}s)"

attempt=1
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
    if ! docker ps -q -f "name=^/${CONTAINER}\$" | grep -q .; then
        echo "ERROR: Container '${CONTAINER}' is not running"
        docker logs "${CONTAINER}" --tail 120 2>&1 || true
        exit 1
    fi

    health_status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${CONTAINER}" 2>/dev/null || echo "none")"
    if [ "${health_status}" = "healthy" ]; then
        echo "==> Container '${CONTAINER}' is healthy (Docker HEALTHCHECK)"
        exit 0
    fi

    if docker exec "${CONTAINER}" python -c "
import json, sys, urllib.request
mode = '${MODE}'
try:
    with urllib.request.urlopen('${HEALTH_URL}', timeout=8) as r:
        body = r.read().decode()
        if r.status != 200:
            sys.exit(1)
        if mode == 'http':
            sys.exit(0)
        data = json.loads(body) if body.strip().startswith('{') else {}
        sys.exit(0 if data.get('status') == 'healthy' else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        echo "==> Container '${CONTAINER}' passed in-container HTTP health check"
        exit 0
    fi

    echo "    attempt ${attempt}/${MAX_ATTEMPTS}: docker_health=${health_status}"
    sleep "${INTERVAL}"
    attempt=$((attempt + 1))
done

echo "ERROR: Timed out waiting for '${CONTAINER}' to become healthy"
docker inspect "${CONTAINER}" --format='{{json .State.Health}}' 2>/dev/null || true
docker logs "${CONTAINER}" --tail 150 2>&1 || true
exit 1
