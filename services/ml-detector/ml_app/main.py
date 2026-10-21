"""API technique du détecteur : health/metrics uniquement (aucune API d'inférence utilisateur)."""

from __future__ import annotations

import json
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config import Settings
from .detector import Detector
from .metrics import Metrics
from .model import ModelIntegrityError, load_verified
from .outbox import Sender
from .prom import Prometheus

log = logging.getLogger("ml-detector")


class _Json(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        try:
            payload = json.loads(message)
            if not isinstance(payload, dict):
                raise ValueError
        except ValueError:
            payload = {"event_type": "LOG", "message": message}
        payload.update(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=record.levelname,
            service="ml-detector",
        )
        return json.dumps(payload)


def _configure_logging(log_dir: Path | None) -> None:
    log.setLevel(logging.INFO)
    log.propagate = False
    if log.handlers:
        return
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(log_dir / "events.jsonl", maxBytes=10 * 1024 * 1024, backupCount=4)
        )
    for handler in handlers:
        handler.setFormatter(_Json())
        log.addHandler(handler)


def create_app(settings: Settings | None = None, start_loop: bool = True) -> FastAPI:
    settings = settings or Settings.load()
    _configure_logging(settings.log_dir)
    metrics = Metrics()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.detector = None
        app.state.model_error = ""
        try:
            model = load_verified(settings.model_dir, settings.pinned_sha256)
        except (ModelIntegrityError, OSError, ValueError) as exc:
            # readiness = false : jamais de détection avec un modèle non vérifié.
            app.state.model_error = str(exc)
            log.error("model not loaded: %s", exc)
        else:
            detector = Detector(
                model,
                Prometheus(settings.prometheus_url),
                Sender(settings.incident_url, settings.anomaly_token, settings.state_dir),
                metrics,
                settings,
            )
            app.state.detector = detector
            if start_loop:
                threading.Thread(target=detector.run, name="detector", daemon=True).start()
        yield
        if app.state.detector:
            app.state.detector.stop.set()

    app = FastAPI(
        title="ml-detector",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        detector = getattr(app.state, "detector", None)
        if detector is None:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "detail": app.state.model_error or "MODEL_NOT_LOADED",
                },
            )
        # modèle chargé + métriques fraîches (ML_DESIGN / SERVICE_CATALOG)
        if start_loop and not detector.fresh:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "detail": detector.last_error or "NO_FRESH_WINDOW",
                    "model_version": detector.model.version,
                },
            )
        return {
            "status": "ok",
            "model_version": detector.model.version,
            "threshold": detector.model.threshold,
        }

    @app.get("/metrics")
    def prom_metrics():
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    return app


def app_factory() -> FastAPI:  # uvicorn --factory ml_app.main:app_factory
    return create_app()
