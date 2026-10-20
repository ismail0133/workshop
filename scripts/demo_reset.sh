#!/usr/bin/env bash
# Demo reset: put the platform back in a known-good state before a rehearsal / the recorded clip.
#
#   bash scripts/demo_reset.sh            soft reset (default, keeps data)
#   bash scripts/demo_reset.sh --obs      soft reset + (re)start Prometheus/Loki/Alloy/Grafana
#   bash scripts/demo_reset.sh --hard     DELETES every volume (db, logs, grafana) and rebuilds from the seeds
#
# Soft reset:
#   1. empties the edge blocklist (keeps its comments) and waits until the WAF applied it
#   2. (re)starts postgres, auth-service, payment-api, frontend and the WAF, waiting for "healthy"
#   3. checks through the WAF: readiness, front, login, one 0.01 EUR payment (new + replay)
# Exit code 0 only if everything is OK.
set -u
cd "$(dirname "$0")/.."

HARD=0; OBS=0
for a in "$@"; do
    case "$a" in
        --hard) HARD=1 ;;
        --obs)  OBS=1 ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        *) echo "unknown option: $a (try --help)"; exit 2 ;;
    esac
done

FILES=(-f docker-compose.yml -f docker-compose.edge.yml)
[ -f docker-compose.grafana-ui.yml ] && FILES+=(-f docker-compose.grafana-ui.yml)
DC=(docker compose "${FILES[@]}" --profile foundation)

BL="infrastructure/waf/blocklist/blocklist.txt"
PWFILE="infrastructure/secrets/runtime/demo_alice_password"
URL="http://127.0.0.1:${WAF_HTTP_PORT:-8090}"
ACC1="20000000-0000-4000-8000-000000000001"
ACC2="20000000-0000-4000-8000-000000000002"

PASS=0; FAIL=0
ok()   { echo "  OK    $1"; PASS=$((PASS+1)); }
ko()   { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }
step() { echo; echo "== $1"; }
die()  { echo "  ABORT $1"; exit 1; }

# ---------------------------------------------------------------- HARD reset
if [ "$HARD" -eq 1 ]; then
    step "HARD reset"
    echo "  This deletes ALL volumes of the project (database, logs, Grafana, Loki...)."
    read -r -p "  Type RESET to continue: " ans
    [ "$ans" = "RESET" ] || die "cancelled"
    "${DC[@]}" down -v --remove-orphans || die "down -v failed"
    "${DC[@]}" up -d --wait postgres || die "postgres did not become healthy"
    "${DC[@]}" run --rm db-tools python scripts/stage_secrets.py \
        && "${DC[@]}" run --rm db-tools python -m database.bootstrap \
        && "${DC[@]}" run --rm db-tools alembic upgrade head \
        && "${DC[@]}" run --rm db-tools python -m database.seeds.demo \
        || die "database initialisation failed"
    # Linux-host permission quirks seen on Docker Desktop / WSL2
    [ -f infrastructure/secrets/runtime/grafana_password ] && chmod 644 infrastructure/secrets/runtime/grafana_password
    "${DC[@]}" up --no-start alloy >/dev/null 2>&1
    AV=$(docker volume ls -q --filter name=alloy_data | head -n 1)
    [ -n "$AV" ] && docker run --rm --user root --entrypoint chmod -v "$AV":/data grafana/alloy:v1.10.2 777 /data >/dev/null 2>&1
    OBS=1
    ok "database rebuilt from seeds"
fi

# ---------------------------------------------------------------- 1. blocklist
step "1. Edge blocklist"
mkdir -p "$(dirname "$BL")"
if [ -f "$BL" ]; then grep -E '^[[:space:]]*#' "$BL" > "$BL.tmp" || true; else : > "$BL.tmp"; fi
mv -f "$BL.tmp" "$BL"
ok "blocklist.txt emptied (comments kept)"

# ---------------------------------------------------------------- 2. services
step "2. Services"
"${DC[@]}" up -d --wait postgres || die "postgres is not healthy (disk disconnected? see: docker compose logs postgres)"
ok "postgres healthy"
SERVICES=(auth-service payment-api frontend waf)
[ "$OBS" -eq 1 ] && SERVICES+=(waf-exporter prometheus loki alloy grafana)
if "${DC[@]}" up -d --wait "${SERVICES[@]}"; then
    ok "services healthy: ${SERVICES[*]}"
else
    ko "some services are not healthy (see: ${DC[*]} ps)"
fi

# ---------------------------------------------------------------- 3. blocklist applied
step "3. WAF blocklist applied"
APPLIED=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
    S=$("${DC[@]}" exec -T waf wget -qO- http://127.0.0.1:8081/blocklist-status 2>/dev/null || true)
    if echo "$S" | grep -q '"blocked_ips":0,"blocked_user_agents":0'; then APPLIED=1; break; fi
    sleep 1
done
[ "$APPLIED" -eq 1 ] && ok "WAF reports 0 blocked IP / 0 blocked User-Agent" || ko "WAF still reports blocked entries: $S"

# ---------------------------------------------------------------- 4. business checks
step "4. Business checks through the WAF ($URL)"
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$@"; }
for _ in 1 2 3 4 5 6; do [ "$(code "$URL/health/ready")" = "200" ] && break; sleep 2; done
[ "$(code "$URL/health/ready")" = "200" ] && ok "payment readiness (200)" || ko "payment readiness"
[ "$(code "$URL/")" = "200" ]             && ok "frontend served (200)"   || ko "frontend"
[ "$(code "$URL/metrics")" = "404" ]      && ok "/metrics hidden (404)"   || ko "/metrics exposed"

if [ -r "$PWFILE" ]; then
    TOKEN=$(curl -s --max-time 8 -X POST "$URL/api/auth/login" -H 'Content-Type: application/json' \
        -d "{\"email\":\"alice@resilience.test\",\"password\":\"$(cat "$PWFILE")\"}" \
        | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)
    if [ -n "$TOKEN" ]; then
        ok "login alice"
        KEY="reset-$(date +%s)-$RANDOM"
        BODY="{\"source_account_id\":\"$ACC1\",\"destination_account_id\":\"$ACC2\",\"amount_minor\":1,\"currency\":\"EUR\"}"
        pay() { code -X POST "$URL/api/payments" -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $KEY" -H 'Content-Type: application/json' -d "$BODY"; }
        [ "$(pay)" = "201" ] && ok "payment 0.01 EUR accepted (201)" || ko "payment"
        [ "$(pay)" = "200" ] && ok "same Idempotency-Key replayed (200, not duplicated)" || ko "replay"
    else
        ko "login alice (is the database seeded with the current secrets? try --hard)"
    fi
else
    ko "missing $PWFILE (run scripts/prepare_secrets.py)"
fi

# ---------------------------------------------------------------- summary
echo
echo "RESULT: $PASS ok, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    echo "Ready for the demo.  Site: $URL  |  HTTPS: https://<WAF_BIND_IP>:${WAF_HTTPS_PORT:-8443}"
    [ "$OBS" -eq 1 ] && echo "Grafana: http://127.0.0.1:3000 (admin / infrastructure/secrets/runtime/grafana_password)"
fi
[ "$FAIL" -eq 0 ]
