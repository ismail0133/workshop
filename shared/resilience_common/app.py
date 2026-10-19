import json
import logging
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    ProcessCollector,
    generate_latest,
)
from sqlalchemy import text

from .config import Settings
from .db import create_database
from .errors import APIError, register_errors
from .schemas import Health


class RateLimiter:
    def __init__(self, limit: int):
        self.limit, self.entries, self.lock = limit, {}, Lock()

    def check(self, key: str):
        now = time.monotonic()
        with self.lock:
            # Bound memory and expire inactive sources.
            self.entries = {k: v for k, v in self.entries.items() if v and v[-1] > now - 60}
            if key not in self.entries and len(self.entries) >= 2048:
                raise APIError(429, "RATE_LIMITED", "Trop de sources actives")
            attempts = self.entries.setdefault(key, deque())
            while attempts and attempts[0] <= now - 60:
                attempts.popleft()
            if len(attempts) >= self.limit:
                raise APIError(429, "RATE_LIMITED", "Trop de tentatives")
            attempts.append(now)


def create_app(service: str) -> FastAPI:
    settings = Settings.load(service)
    engine, sessions = create_database(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title=service, version="0.2.0", lifespan=lifespan)
    app.state.settings, app.state.engine, app.state.sessions = settings, engine, sessions
    app.state.limiter = RateLimiter(settings.login_rate_limit)
    register_errors(app)
    registry = CollectorRegistry()
    ProcessCollector(registry=registry)
    labels = ["service", "route", "method", "status_class", "traffic"]
    requests = Counter("http_requests_total", "Completed requests", labels, registry=registry)
    duration = Histogram(
        "http_request_duration_seconds",
        "Request duration",
        labels[:-2] + ["traffic"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
        registry=registry,
    )
    active = Gauge(
        "http_requests_in_progress", "Requests being handled", ["service"], registry=registry
    )
    attempts = Counter(
        "payment_attempts_total", "Business payment results", ["outcome"], registry=registry
    )
    for outcome in ("success", "failure"):
        attempts.labels(outcome).inc(0)
    app.state.payment_attempts = attempts
    if service == "payment-api":
        Gauge("payment_cpu_limit_cores", "Configured CPU quota", registry=registry).set(
            float(os.getenv("CPU_LIMIT_CORES", ".75"))
        )
        Gauge("payment_memory_limit_bytes", "Configured memory limit", registry=registry).set(
            int(os.getenv("MEMORY_LIMIT_BYTES", "402653184"))
        )
        for route, method in [
            ("/api/accounts", "GET"),
            ("/api/accounts/{id}", "GET"),
            ("/api/payments", "GET"),
            ("/api/payments", "POST"),
            ("/api/payments/{id}", "GET"),
        ]:
            for status in ("2xx", "4xx", "5xx"):
                requests.labels(service, route, method, status, "business").inc(0)
    logger = logging.getLogger(service)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        stream = logging.StreamHandler()
        logger.addHandler(stream)
        if log_dir := os.getenv("LOG_DIR"):
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            logger.addHandler(
                RotatingFileHandler(
                    Path(log_dir) / "events.jsonl", maxBytes=10 * 1024 * 1024, backupCount=4
                )
            )

    @app.middleware("http")
    async def telemetry(request: Request, call_next):
        # No ingress trust in phase 1; never accept a caller-supplied correlation id.
        request.state.request_id = str(uuid4())
        started = time.perf_counter()
        active.labels(service).inc()
        try:
            length = request.headers.get("content-length")
            if length is not None and (not length.isdigit() or int(length) > 16384):
                response = JSONResponse(
                    status_code=413,
                    content={
                        "code": "BODY_TOO_LARGE",
                        "message": "Corps trop volumineux",
                        "request_id": request.state.request_id,
                    },
                )
            else:
                # Also enforce the limit for chunked HTTP bodies.
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 16384:
                        break
                if len(body) > 16384:
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "code": "BODY_TOO_LARGE",
                            "message": "Corps trop volumineux",
                            "request_id": request.state.request_id,
                        },
                    )
                else:
                    request._body = bytes(body)
                    response = await call_next(request)
        except Exception:
            # No exception repr: database URLs and user input must never enter logs.
            response = JSONResponse(
                status_code=500,
                content={
                    "code": "INTERNAL_ERROR",
                    "message": "Erreur interne",
                    "request_id": request.state.request_id,
                },
            )
        finally:
            active.labels(service).dec()
        elapsed = time.perf_counter() - started
        route = getattr(request.scope.get("route"), "path", "unmatched")
        traffic = "business" if route.startswith("/api/") else "health"
        status_class = f"{response.status_code // 100}xx"
        requests.labels(service, route, request.method, status_class, traffic).inc()
        duration.labels(service, route, request.method, traffic).observe(elapsed)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "INFO",
                    "service": service,
                    "event_type": "HTTP_REQUEST",
                    "request_id": request.state.request_id,
                    "route": route,
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": round(elapsed * 1000, 3),
                }
            )
        )
        return response

    @app.get("/metrics", include_in_schema=True)
    def metrics():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return app


def health(request: Request, ready: bool = False) -> Health:
    if ready:
        with request.app.state.engine.connect() as conn:
            # Schema visibility is verified under the actual least-privilege role.
            table = (
                "auth.users"
                if request.app.state.settings.service == "auth-service"
                else "bank.accounts"
            )
            conn.execute(text(f"SELECT id FROM {table} LIMIT 1"))
            revision = conn.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalar_one()
            if revision != "0002_roles":
                raise APIError(503, "SCHEMA_NOT_READY", "Version de schéma incompatible")
    return Health(
        status="ok",
        service=request.app.state.settings.service,
        checked_at=datetime.now(timezone.utc),
    )
