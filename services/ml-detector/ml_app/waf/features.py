"""Fenêtres glissantes par User-Agent et caractéristiques de comportement.

Fenêtre = [fin - W, fin) ; les fins tombent sur une grille alignée sur l'époque (pas de STEP_S).
Les 7 caractéristiques décrivent un comportement, jamais une identité :
débit, part de 4xx, part de 5xx, nombre d'URI distinctes, concentration sur l'URI dominante,
durée moyenne côté WAF (ms), part de POST.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass

from . import STEP_S, WINDOW_S
from .logs import Request

FEATURE_NAMES = (
    "req_per_s",
    "share_4xx",
    "share_5xx",
    "distinct_uris",
    "top_uri_share",
    "mean_duration_ms",
    "share_post",
)
LOG1P_FEATURES = ("req_per_s", "distinct_uris", "mean_duration_ms")
MAX_ENTITIES = 500  # User-Agent distincts analysés par fenêtre (borne mémoire/CPU)


@dataclass(frozen=True, slots=True)
class Step:
    end: float
    entities: dict  # ua -> (n_requests, vecteur de caractéristiques)
    overflow: int = 0  # User-Agent ignorés au-delà de MAX_ENTITIES


def vector(requests: list[Request], window_s: float = WINDOW_S) -> list[float]:
    n = len(requests)
    if n == 0:
        raise ValueError("fenêtre vide")
    uris = Counter(r.path for r in requests)
    return [
        n / window_s,
        sum(400 <= r.status < 500 for r in requests) / n,
        sum(r.status >= 500 for r in requests) / n,
        float(len(uris)),
        max(uris.values()) / n,
        math.fsum(r.duration_ms for r in requests) / n,
        sum(r.method == "POST" for r in requests) / n,
    ]


def entities_in_window(requests: list[Request], window_s: float, max_entities: int = MAX_ENTITIES) -> tuple[dict, int]:
    groups: dict[str, list[Request]] = defaultdict(list)
    for request in requests:
        groups[request.ua].append(request)
    overflow = 0
    if len(groups) > max_entities:
        keep = sorted(groups, key=lambda ua: (-len(groups[ua]), ua))[:max_entities]
        overflow = len(groups) - max_entities
        groups = {ua: groups[ua] for ua in keep}
    return {ua: (len(rs), vector(rs, window_s)) for ua, rs in groups.items()}, overflow


def first_boundary(first_ts: float, step_s: float = STEP_S) -> float:
    return (math.floor(first_ts / step_s) + 1) * step_s


def build_steps(
    requests: list[Request], window_s: float = WINDOW_S, step_s: float = STEP_S, *, inside_only: tuple | None = None
) -> list[Step]:
    """Toutes les fenêtres couvrant `requests` (triées). `inside_only=(a, b)` ne garde que les fenêtres
    entièrement comprises dans [a, b) : une fenêtre à cheval sur deux jeux n'appartient à aucun."""
    if not requests:
        return []
    stamps = [r.ts for r in requests]
    steps: list[Step] = []
    end = first_boundary(stamps[0], step_s)
    last = math.floor(stamps[-1] / step_s) * step_s + window_s
    while end <= last:
        if inside_only is None or (end - window_s >= inside_only[0] and end <= inside_only[1]):
            lo, hi = bisect_left(stamps, end - window_s), bisect_left(stamps, end)
            entities, overflow = entities_in_window(requests[lo:hi], window_s)
            steps.append(Step(end, entities, overflow))
        end += step_s
    return steps
