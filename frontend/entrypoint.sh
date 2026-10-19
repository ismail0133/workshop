#!/bin/sh
set -eu
: "${AUTH_UPSTREAM:=http://auth-service:8001}"
: "${PAYMENT_UPSTREAM:=http://payment-api:8000}"
export AUTH_UPSTREAM PAYMENT_UPSTREAM
envsubst '$AUTH_UPSTREAM $PAYMENT_UPSTREAM' < /etc/nginx/frontend.template > /tmp/frontend.conf
exec nginx -g 'daemon off;'
