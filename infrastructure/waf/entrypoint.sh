#!/bin/sh
set -u
. /opt/waf/blocklist.sh

mkdir -p /tmp/waf/tls /tmp/nginx

# ---- TLS: mounted certs if present, otherwise a throw-away self-signed one ----
if [ -r /certs/tls.crt ] && [ -r /certs/tls.key ]; then
    cp /certs/tls.crt /tmp/waf/tls/tls.crt
    cp /certs/tls.key /tmp/waf/tls/tls.key
else
    openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
        -keyout /tmp/waf/tls/tls.key -out /tmp/waf/tls/tls.crt \
        -subj "/CN=resilience-alpha-edge" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1 \
        || echo '{"service":"waf","event":"TLS_SELFSIGNED_FAILED"}' >&2
fi
chmod 600 /tmp/waf/tls/tls.key 2>/dev/null

# ---- Blocklist: render + `nginx -t` before nginx even starts ------------------
init_blocklist
watch_loop &

exec nginx -g 'daemon off;'
