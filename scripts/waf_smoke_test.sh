#!/usr/bin/env bash
# Smoke test of the Nginx edge. Run from the repo root (Ubuntu/WSL):
#   docker compose -f docker-compose.yml -f docker-compose.edge.yml up -d --build --wait waf auth-service
#   bash scripts/waf_smoke_test.sh
# Optional: WAF_URL=http://127.0.0.1:8090  EMAIL=alice@resilience.test
set -u
cd "$(dirname "$0")/.."

# docker compose reads .env itself; the script must see the same WAF_BIND_IP
if [ -z "${WAF_BIND_IP:-}" ] && [ -f .env ]; then
    WAF_BIND_IP=$(grep -E '^WAF_BIND_IP=' .env | tail -n 1 | cut -d= -f2 | tr -d '\r"'"'"' ')
fi

WAF_URL="${WAF_URL:-http://127.0.0.1:${WAF_HTTP_PORT:-8090}}"
EMAIL="${EMAIL:-alice@resilience.test}"
PWFILE="infrastructure/secrets/runtime/demo_alice_password"
BL="infrastructure/waf/blocklist/blocklist.txt"
DC="docker compose -f docker-compose.yml -f docker-compose.edge.yml"
SRC="00000000-0000-0000-0000-000000000000"
ACC1="20000000-0000-4000-8000-000000000001"
ACC2="20000000-0000-4000-8000-000000000002"

PASS=0; FAIL=0
ok()   { echo "  PASS  $1"; PASS=$((PASS+1)); }
ko()   { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }
check() { # name expected actual
    if [ "$2" = "$3" ]; then ok "$1 (HTTP $3)"; else ko "$1 (expected $2, got $3)"; fi
}
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$@"; }
BL_BACKUP=$(mktemp); cp "$BL" "$BL_BACKUP"
cleanup() { cp "$BL_BACKUP" "$BL"; rm -f "$BL_BACKUP"; }
trap cleanup EXIT

wait_applied() { # wait until /blocklist-status shows a new sha (max 8 s)
    local before="$1" i s
    for i in 1 2 3 4 5 6 7 8; do
        sleep 1
        s=$($DC exec -T waf wget -qO- http://127.0.0.1:8081/blocklist-status 2>/dev/null)
        [ -n "$s" ] && [ "$(echo "$s" | python3 -c 'import sys,json;print(json.load(sys.stdin)["updated_at"])' 2>/dev/null)" != "$before" ] && return 0
    done
    return 1
}
status_field() { $DC exec -T waf wget -qO- http://127.0.0.1:8081/blocklist-status | python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }

echo "== 1. Edge and routing"
check "edge health"                 200 "$(code "$WAF_URL/edge/health")"
check "payment readiness relayed"   200 "$(code "$WAF_URL/health/ready")"
check "frontend served (/)"         200 "$(code "$WAF_URL/")"
check "frontend status route"       200 "$(code "$WAF_URL/status/payment")"
check "unknown /api path hidden"    404 "$(code "$WAF_URL/api/auth/admin")"
check "/metrics hidden"             404 "$(code "$WAF_URL/metrics")"
check "/docs hidden"                404 "$(code "$WAF_URL/docs")"
check "/health hidden"              404 "$(code "$WAF_URL/health")"
check "path traversal to /metrics"  404 "$(code --path-as-is "$WAF_URL/api/../metrics")"
check "PUT refused"                 405 "$(code -X PUT "$WAF_URL/api/payments")"
check "no token -> 401"             401 "$(code "$WAF_URL/api/accounts")"

echo "== 2. Business flow through the edge"
[ -r "$PWFILE" ] || { echo "  missing $PWFILE (run scripts/prepare_secrets.py)"; exit 1; }
TOKEN=$(curl -s --max-time 8 -X POST "$WAF_URL/api/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$(cat "$PWFILE")\"}" \
    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)
if [ -n "$TOKEN" ]; then ok "login via edge (token ${#TOKEN} chars)"; else ko "login via edge"; fi
check "GET /api/accounts"           200 "$(code "$WAF_URL/api/accounts" -H "Authorization: Bearer $TOKEN")"
KEY="smoke-$(date +%s)-$RANDOM"
BODY="{\"source_account_id\":\"$ACC1\",\"destination_account_id\":\"$ACC2\",\"amount_minor\":1,\"currency\":\"EUR\"}"
pay() { code -X POST "$WAF_URL/api/payments" -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $KEY" -H 'Content-Type: application/json' -d "$BODY"; }
check "payment (new)"               201 "$(pay)"
check "payment (idempotent replay)" 200 "$(pay)"
RID=$(curl -s -D - -o /dev/null "$WAF_URL/health/ready" | tr -d '\r' | awk 'tolower($1)=="x-request-id:"{print $2}')
[ -n "$RID" ] && ok "X-Request-ID returned ($RID)" || ko "X-Request-ID missing"

echo "== 3. Access log (JSON)"
LAST=$($DC exec -T waf tail -n 1 /var/log/resilience/waf/access.jsonl 2>/dev/null)
if echo "$LAST" | python3 -c 'import sys,json;d=json.loads(sys.stdin.read());assert "client_ip" in d and "status" in d' 2>/dev/null; then
    ok "access.jsonl valid JSON"
else ko "access.jsonl not valid JSON: $LAST"; fi
if echo "$LAST" | grep -qi authorization; then ko "Authorization leaked in logs"; else ok "no Authorization in logs"; fi
SEEN_IP=$(echo "$LAST" | python3 -c 'import sys,json;print(json.loads(sys.stdin.read())["client_ip"])' 2>/dev/null)
echo "  info  source IP seen by the edge for this client: ${SEEN_IP:-?}"

if ! $DC exec -T waf grep -q BROWSER_UA_SAMPLE /opt/waf/blocklist.sh 2>/dev/null; then
    echo "  WARN  the running WAF image is OLD: rebuild with  $DC up -d --build --wait waf"
fi
echo "== 4. Block / unblock cycle by User-Agent (source IP is masked behind Docker Desktop)"
case "$SEEN_IP" in
    172.1[6-9].*|172.2[0-9].*|172.3[0-1].*|192.168.65.*) echo "  info  client IP is a Docker gateway ($SEEN_IP): blocking is UA-based" ;;
esac
BOT="WafSmokeBot/1.0"
bot() { curl -s -o /dev/null -w '%{http_code}' --max-time 8 -A "$BOT" "$WAF_URL/edge/health"; }
check "bot before block"              200 "$(bot)"
T0=$(status_field updated_at)
echo "ua:WafSmokeBot" >> "$BL"
wait_applied "$T0" && ok "blocklist applied (sha $(status_field applied_sha | cut -c1-12))" || ko "blocklist not applied within 8 s"
check "blocked UA -> 403"             403 "$(bot)"
check "normal browser UA still ok"    200 "$(code -A 'Mozilla/5.0 Chrome/155 Safari/537.36' "$WAF_URL/edge/health")"
check "default curl still ok"         200 "$(code "$WAF_URL/edge/health")"
cp "$BL_BACKUP" "$BL"; T1=$(status_field updated_at)
wait_applied "$T1" >/dev/null
check "unblocked UA -> 200"           200 "$(bot)"
T1=$(status_field updated_at)
printf 'ua:Chrome\nua:Mozilla\nua:abc\n' >> "$BL"
wait_applied "$T1" >/dev/null
check "dangerous UA entries refused (browser still ok)" 200 "$(code -A 'Mozilla/5.0 Chrome/155 Safari/537.36' "$WAF_URL/edge/health")"
cp "$BL_BACKUP" "$BL"; T1=$(status_field updated_at); wait_applied "$T1" >/dev/null

echo "== 5. Invalid entries must not break the edge"
T2=$(status_field updated_at)
printf '999.1.1.1\n1.2.3.4; }\nua:bad ua\n1:2:3:4:5:6:7:8:9\n' >> "$BL"
wait_applied "$T2" >/dev/null
check "edge still serving"          200 "$(code "$WAF_URL/edge/health")"
echo "  info  junk lines are dropped one by one (see 'docker compose logs waf' -> REJECTED_ENTRY); last_error='$(status_field last_error)'"
cp "$BL_BACKUP" "$BL"; T3=$(status_field updated_at); wait_applied "$T3" >/dev/null
check "recovered after cleanup"     200 "$(code "$WAF_URL/edge/health")"

echo "== 6. HTTPS (self-signed)"
# From WSL the Windows hotspot address is not reachable (the firewall rule only allows
# 192.168.137.0/24): use the Windows curl through WSL interop when available.
HTTPS_URL="https://${WAF_BIND_IP:-127.0.0.1}:${WAF_HTTPS_PORT:-8443}/edge/health"
if command -v curl.exe >/dev/null 2>&1; then
    HC=$(curl.exe -sk -o /dev/null -w '%{http_code}' --max-time 8 "$HTTPS_URL" | tr -d '\r')
else
    HC=$(code -k "$HTTPS_URL")
fi
check "https edge health"           200 "$HC"

echo
echo "RESULT: $PASS passed, $FAIL failed"
cat <<'EOF'

Manual check still required (cannot be done from the host itself):
  From the ATTACKER PC:   curl -sk https://<host-hotspot-ip>:8443/edge/health
  Then on the host:       docker compose -f docker-compose.yml -f docker-compose.edge.yml exec waf tail -n 1 /var/log/resilience/waf/access.jsonl
  -> "client_ip" is expected to be 172.x (Docker Desktop masks the real source): block by "ua:" entries, see README "Source IP".
EOF
[ "$FAIL" -eq 0 ]
