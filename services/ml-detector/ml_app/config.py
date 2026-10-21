from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _read_secret(path_var: str) -> str | None:
    path = os.getenv(path_var)
    if not path:
        return None
    return Path(path).read_text().strip() or None


@dataclass(frozen=True)
class Settings:
    prometheus_url: str
    incident_url: str | None  # None => mode « dry-run » (journalise sans envoyer)
    model_dir: Path
    pinned_sha256: str | None
    state_dir: Path
    log_dir: Path | None
    anomaly_token: str | None
    interval_seconds: float
    window_seconds: int
    consecutive: int
    cooldown_seconds: float

    @staticmethod
    def load() -> "Settings":
        log_dir = os.getenv("LOG_DIR")
        return Settings(
            prometheus_url=os.getenv("PROMETHEUS_URL", "http://prometheus:9090"),
            incident_url=os.getenv("INCIDENT_URL") or None,
            model_dir=Path(os.getenv("MODEL_DIR", "/models/current")),
            pinned_sha256=os.getenv("MODEL_SHA256") or None,
            state_dir=Path(os.getenv("STATE_DIR", "/var/lib/ml")),
            log_dir=Path(log_dir) if log_dir else None,
            anomaly_token=_read_secret("ANOMALY_TOKEN_FILE"),
            interval_seconds=float(os.getenv("ML_INTERVAL_SECONDS", "5")),
            window_seconds=int(os.getenv("ML_WINDOW_SECONDS", "15")),
            consecutive=int(os.getenv("ML_CONSECUTIVE", "2")),
            cooldown_seconds=float(os.getenv("ML_COOLDOWN_SECONDS", "60")),
        )
