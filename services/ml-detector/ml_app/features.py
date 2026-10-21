"""Définition des 8 caractéristiques, requêtes PromQL et validation de fenêtre.

Source de vérité : docs/ml/ML_DESIGN.md. Une fenêtre invalide n'est jamais « réparée » :
pas de forward-fill, pas de zéro inventé. L'absence de donnée est un état (DATA_UNAVAILABLE).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

FEATURE_NAMES: tuple[str, ...] = (
    "request_rate",
    "http_5xx_rate",
    "http_4xx_rate",
    "latency_p95_ms",
    "cpu_usage_percent",
    "memory_usage_percent",
    "active_requests",
    "payment_failure_rate",
)

# Bornes du contrat events.schema.json (Features) : (min, max) ; None = non borné.
BOUNDS: dict[str, tuple[float, float | None]] = {
    "request_rate": (0.0, None),
    "http_5xx_rate": (0.0, 1.0),
    "http_4xx_rate": (0.0, 1.0),
    "latency_p95_ms": (0.0, None),
    "cpu_usage_percent": (0.0, 100.0),
    "memory_usage_percent": (0.0, 100.0),
    "active_requests": (0.0, None),
    "payment_failure_rate": (0.0, 1.0),
}

# Transformation log1p appliquée dans le pipeline (cf. ML_DESIGN « Préparation »).
LOG1P_FEATURES: tuple[str, ...] = ("request_rate", "latency_p95_ms", "active_requests")

SERVICE = "payment-api"
BIZ = f'service="{SERVICE}",traffic="business"'
W = "{window}"  # remplacé par la fenêtre (ex. 15s)

# PromQL conceptuel de ML_DESIGN, rendu exécutable. `or vector(0)` n'est utilisé QUE là où
# l'absence de série signifie réellement « aucun événement » (compteurs 5xx/4xx initialisés à 0).
QUERIES: dict[str, str] = {
    "request_rate": f"sum(rate(http_requests_total{{{BIZ}}}[{W}]))",
    "http_5xx_rate": (
        f'sum(rate(http_requests_total{{{BIZ},status_class="5xx"}}[{W}]))'
        f" / sum(rate(http_requests_total{{{BIZ}}}[{W}]))"
    ),
    "http_4xx_rate": (
        f'sum(rate(http_requests_total{{{BIZ},status_class="4xx"}}[{W}]))'
        f" / sum(rate(http_requests_total{{{BIZ}}}[{W}]))"
    ),
    "latency_p95_ms": (
        f"1000 * histogram_quantile(0.95, sum by(le)"
        f"(rate(http_request_duration_seconds_bucket{{{BIZ}}}[{W}])))"
    ),
    "cpu_usage_percent": (
        f'100 * rate(process_cpu_seconds_total{{job="{SERVICE}"}}[{W}])'
        f' / scalar(payment_cpu_limit_cores{{job="{SERVICE}"}})'
    ),
    "memory_usage_percent": (
        f'100 * process_resident_memory_bytes{{job="{SERVICE}"}}'
        f' / scalar(payment_memory_limit_bytes{{job="{SERVICE}"}})'
    ),
    "active_requests": f'avg_over_time(http_requests_in_progress{{service="{SERVICE}"}}[{W}])',
    "payment_failure_rate": (
        'sum(rate(payment_attempts_total{outcome="failure"}[' + W + "]))"
        " / sum(rate(payment_attempts_total[" + W + "]))"
    ),
}

# Requêtes de contrôle de qualité de fenêtre.
QUALITY_QUERIES: dict[str, str] = {
    "samples": f'min(count_over_time(up{{job="{SERVICE}"}}[{W}]))',
    "up": f'min(up{{job="{SERVICE}"}})',
    "age_seconds": f'time() - max(timestamp(up{{job="{SERVICE}"}}))',
    "counter_resets": f"sum(resets(http_requests_total{{{BIZ}}}[{W}]))",
    "payment_attempts": f"sum(increase(payment_attempts_total[{W}]))",
}

MIN_SAMPLES = 3
MAX_AGE_SECONDS = 10.0


def render(query: str, window_seconds: int) -> str:
    return query.replace("{window}", f"{window_seconds}s")


@dataclass
class FeatureWindow:
    """Résultat d'extraction : soit un vecteur valide, soit une raison d'invalidité."""

    start: float
    end: float
    values: dict[str, float] = field(default_factory=dict)
    valid: bool = False
    reason: str = ""

    def vector(self) -> list[float]:
        return [self.values[name] for name in FEATURE_NAMES]


def _finite(value) -> bool:
    return value is not None and isinstance(value, (int, float)) and math.isfinite(value)


def validate_quality(quality: dict[str, float | None]) -> str:
    """Retourne '' si la fenêtre est exploitable, sinon un code de raison (DATA_UNAVAILABLE)."""
    if not _finite(quality.get("up")) or quality["up"] < 1:
        return "TARGET_DOWN"
    if not _finite(quality.get("samples")) or quality["samples"] < MIN_SAMPLES:
        return "TOO_FEW_SAMPLES"
    age = quality.get("age_seconds")
    if not _finite(age) or age > MAX_AGE_SECONDS or age < -1:
        return "STALE_SERIES"
    resets = quality.get("counter_resets")
    if not _finite(resets) or resets > 0:
        return "COUNTER_RESET"
    return ""


def clip(name: str, value: float) -> float:
    low, high = BOUNDS[name]
    value = max(low, value)
    return min(high, value) if high is not None else value


def build_window(
    start: float,
    end: float,
    raw: dict[str, float | None],
    quality: dict[str, float | None],
) -> FeatureWindow:
    """Assemble une fenêtre. Toute valeur manquante/NaN/Inf invalide la fenêtre entière."""
    window = FeatureWindow(start=start, end=end)
    reason = validate_quality(quality)
    if reason:
        window.reason = reason
        return window
    if not _finite(raw.get("request_rate")) or raw["request_rate"] <= 0:
        # Ratio 5xx/4xx indéfini sans trafic ; le protocole maintient un client normal.
        window.reason = "NO_TRAFFIC"
        return window
    if not _finite(quality.get("payment_attempts")) or quality["payment_attempts"] <= 0:
        window.reason = "NO_PAYMENT_ATTEMPT"
        return window
    values: dict[str, float] = {}
    for name in FEATURE_NAMES:
        value = raw.get(name)
        if not _finite(value):
            window.reason = f"MISSING_{name.upper()}"
            return window
        values[name] = clip(name, float(value))
    window.values, window.valid = values, True
    return window
