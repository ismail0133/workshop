"""Boucle de détection : extraction → inférence → règle de déclenchement → événement Anomaly v1."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

from . import SCHEMA_VERSION
from .features import SERVICE, FeatureWindow
from .gate import AlertGate
from .metrics import Metrics
from .model import LoadedModel
from .outbox import Sender
from .prom import Prometheus, PrometheusError

log = logging.getLogger("ml-detector")
_NAMESPACE = uuid.UUID("6f1c2a0e-6d33-4c4e-9b57-1d0a5a1b7e11")


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def build_event(model: LoadedModel, window: FeatureWindow, decision: float, now: float) -> dict:
    """Événement Anomaly v1 (docs/api/events.schema.json).

    event_id est dérivé (UUIDv5) du modèle, du service et de la fin de fenêtre : un retry rejoue
    donc exactement le même identifiant, ce qui rend l'envoi idempotent côté Incident Service.
    Aucun champ source_ip : la source est déduite des logs par le SOC, jamais décidée par le ML.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid5(_NAMESPACE, f"{model.sha256}|{SERVICE}|{window.end:.3f}")),
        "event_type": "ANOMALY_DETECTED",
        "service": SERVICE,
        "timestamp": iso(now),
        "window_start": iso(window.start),
        "window_end": iso(window.end),
        "model": {
            "name": "isolation_forest",
            "version": model.version,
            "artifact_sha256": model.sha256,
            "decision_score": round(decision, 6),
            "threshold": model.threshold,
            "is_anomaly": True,
        },
        "features": {k: round(v, 6) for k, v in window.values.items()},
    }


class Detector:
    def __init__(
        self, model: LoadedModel, prom: Prometheus, sender: Sender, metrics: Metrics, settings
    ):
        self.model, self.prom, self.sender, self.metrics, self.settings = (
            model,
            prom,
            sender,
            metrics,
            settings,
        )
        self.gate = AlertGate(settings.consecutive, cooldown_s=settings.cooldown_seconds)
        self.last_window_ok = 0.0
        self.last_error = ""
        self.stop = threading.Event()
        self.metrics.model_info.labels(self.model.version).set(1)

    def tick(self, at: float | None = None) -> dict | None:
        """Un cycle. Retourne l'événement émis (ou None). Ne lève jamais vers la boucle."""
        now = at if at is not None else time.time()
        try:
            window = self.prom.extract_window(self.settings.window_seconds, at=at)
        except PrometheusError as exc:
            self.last_error = f"PROMETHEUS_{exc}"
            self.metrics.windows.labels("invalid").inc()
            self.gate.reset_run()
            return None
        if not window.valid:
            # DATA_UNAVAILABLE : aucune inférence, aucune remédiation, série interrompue.
            self.last_error = window.reason
            self.metrics.windows.labels("invalid").inc()
            self.gate.reset_run()
            return None
        self.last_error, self.last_window_ok = "", now
        self.metrics.windows.labels("valid").inc()
        with self.metrics.inference.time():
            decision = self.model.decision_score(window.vector())
        self.metrics.score.set(decision)
        self.metrics.threshold.set(self.model.threshold)
        anomalous = decision < self.model.threshold
        if not self.gate.update(anomalous, now):
            return None
        event = build_event(self.model, window, decision, now)
        self.metrics.anomalies.inc()
        outcome = self.sender.send(event)
        self.metrics.deliveries.labels(outcome).inc()
        log.info(
            json.dumps(
                {"event_type": "ANOMALY_EMITTED", "event_id": event["event_id"], "outcome": outcome}
            )
        )
        return event

    def run(self) -> None:
        while not self.stop.is_set():
            started = time.time()
            try:
                self.tick()
                if self.sender.pending():
                    self.sender.flush()
                self.metrics.outbox.set(self.sender.pending())
            except Exception:  # noqa: BLE001 — la boucle ne doit jamais mourir silencieusement
                log.exception("tick failed")
                self.last_error = "INTERNAL_ERROR"
            self.stop.wait(max(0.0, self.settings.interval_seconds - (time.time() - started)))

    @property
    def fresh(self) -> bool:
        return time.time() - self.last_window_ok < 30.0
