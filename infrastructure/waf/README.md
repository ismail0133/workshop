# Edge Nginx (WAF layer)

Reverse proxy in front of `auth-service` and `payment-api`. Single public entry point of the demo.

| Port (host) | Use |
|---|---|
| 8443 (`WAF_HTTPS_PORT`, bound on `WAF_BIND_IP`) | HTTPS, the public entry point (self-signed unless `./infrastructure/waf/certs/tls.{crt,key}` is mounted at `/certs`) |
| 8090 (`WAF_HTTP_PORT`, always 127.0.0.1) | plain HTTP, local tests only |
| 8081 (container only, never published) | `/edge/health`, `/nginx_status`, `/blocklist-status` |

## Start

```bash
docker compose -f docker-compose.yml -f docker-compose.edge.yml up -d --build --wait waf auth-service
bash scripts/waf_smoke_test.sh
```

Open `https://127.0.0.1:8443` (self-signed certificate: accept the warning). For the Attacker PC, set `WAF_BIND_IP=192.168.137.1` (hotspot active) before starting.
For the demo use only these two compose files: `docker-compose.dev.yml` also publishes the APIs on 127.0.0.1:8000/8001 (loopback only, but it bypasses the WAF).

## What the edge does

- Routes `/api/auth/login|me` -> auth-service:8001, `/api/accounts|payments[/id]` -> payment-api:8000 (same whitelist as the frontend), `/health/ready` -> payment-api (validator); any other `/api/...` -> 404; everything else (React app, `/status/*`) -> `frontend:8080`.
- Returns 404 for `/metrics`, `/docs`, `/redoc`, `/openapi.json`, `/health`, `/health/live` (also via `/api/../` tricks). Edge-only health: `/edge/health`.
- Only GET/POST; body <= 16 KiB; short header/body timeouts.
- Rate limits per source IP: global 200 req/s (burst 400), login 10 req/min (burst 5) -> 429 + `Retry-After`.
- `X-Forwarded-For` / `X-Real-IP` are **overwritten** with the address nginx sees (client values are never trusted); `X-Request-ID` is generated.
- No retry on another upstream (a payment is never replayed by the proxy).
- Upstreams are resolved at request time (Docker DNS, 5 s TTL): the edge stays up while a backend is restarted/recovered and answers 503 meanwhile.
- JSON access log -> `/var/log/resilience/waf/access.jsonl` (Alloy already tails it, `service="waf"`) and stdout. No query string, no Authorization header.
- Container hardening: non-root, read-only filesystem, all capabilities dropped, no docker.sock.

## Blocklist contract (for the Remediation Orchestrator)

Write `infrastructure/waf/blocklist/blocklist.txt` (write a temp file then `mv`, so it is atomic):

```
203.0.113.5          # IPv4
10.0.0.0/24          # CIDR
2001:db8::/32        # IPv6
ua:ResilienceAttack  # User-Agent substring [A-Za-z0-9._-]{4,64}, case-insensitive
```

Within ~1-2 s the watcher renders an nginx config, runs `nginx -t`, then `nginx -s reload`.
Invalid lines are dropped one by one and logged (`REJECTED_ENTRY`); if `nginx -t` refuses the whole file, the previous valid blocklist stays active (`REJECTED_CONFIG`).

- `allowlist.txt` protects sources from **IP** blocks (validator host, presenter PC...). Loopback and the Docker gateways (`172.16.0.0/12`, `192.168.65.0/24`) are always protected. A `ua:` block applies to everybody.
- A `ua:` token that would match ordinary browsers (`Chrome`, `Mozilla`, ...) is refused (`REJECTED_ENTRY ... matches normal browsers`).
- Proof of application: `docker compose ... exec waf wget -qO- http://127.0.0.1:8081/blocklist-status`
  -> `{"applied_sha":"...","blocked_ips":1,"last_error":"",...}`. From another container on the `app` network use `http://waf:8081/blocklist-status`.
- Blocked clients get `403 {"code":"EDGE_BLOCKED"}` and `blocked:"1"` in the log.
- To unblock: remove the line.

## Source IP: measured, and what it means

Measured on Docker Desktop (Windows 10, WSL2): a request from another machine on the hotspot is logged with `client_ip` = `172.24.0.1` (the Docker bridge gateway), not `192.168.137.x`. **Blocking by IP is therefore not usable** (it would block every client, the validator included), and the generator refuses it by design (Docker gateways are always protected).

Chosen approach for SC-01: **block by User-Agent** (`ua:` entries).
- The attack tool sends a recognisable `User-Agent` (e.g. `ResilienceAttack/1.0`); `access.jsonl` records `user_agent` for every request, so the detector can extract it from the log.
- The Orchestrator writes `ua:ResilienceAttack` to `blocklist.txt`; the flood then gets `403 EDGE_BLOCKED` while the validator (normal UA) keeps working.
- Limit to state in the dossier: a UA is trivial to change for a real attacker. For the lab it proves the detect -> decide -> act -> verify loop; in production the discriminator would be the real source IP (host with a preserved source address) or an authenticated identity.
- Other options, not done: relay on Windows that forwards the real IP, WSL2 "mirrored" network mode (untested with Docker Desktop + hotspot).

## Known limits / decisions for the team

- No ModSecurity/CRS yet: the block decision is the project's own detector -> blocklist loop. A CRS layer can be added later (e.g. the `owasp/modsecurity-crs` nginx image) without changing the blocklist contract.
- **Login rate limit (known limitation).** The backend limiter (5 logins/min per source) keys on the address it sees, which is always the WAF. `docker-compose.edge.yml` therefore raises `LOGIN_RATE_LIMIT` on auth-service (default 120). The Nginx limit (`edge_login`, 10 logins/min, burst 5) is keyed on `$binary_remote_addr`; because Docker Desktop (WSL2) masks the real client address (see "Source IP"), that bucket is **shared by all clients**, it is NOT a per-client limit. Consequences: legitimate logins are rarely affected (a token lasts 15 min), but a login flood makes everybody get `429` until it stops or is blocked by `ua:`; this is a realistic denial-of-service effect that can be shown in the demo. Passing `X-Forwarded-For` to the backend would not help, it carries the same masked address. A real per-client limit needs the real source address (host that preserves it) or a key the client cannot choose freely (e.g. the account e-mail in the login body, a backend change).
- The edge rate limit (429) happens before the backend, so the flood is visible in `access.jsonl` and in the WAF metrics, **not** in backend Prometheus metrics. The `waf-exporter` sidecar (nginx-prometheus-exporter, `waf:9113`, the target already declared in `prometheus.yml`) exposes `nginx_http_requests_total` (raw request rate, blocked requests included) and `nginx_connections_*`; per-status / per-User-Agent detail comes from the log (Loki).
- The backend ignores a caller-supplied request id (phase-1 comment) while the API contract says the WAF generates it: both ids are logged (`request_id` = edge, `backend_request_id` = backend).
- `access.jsonl` is not rotated (fine for a demo; reset by `docker volume rm` of `waf_logs`).
- Pin the base image digest once the build works (`nginxinc/nginx-unprivileged:1.27-alpine`).
