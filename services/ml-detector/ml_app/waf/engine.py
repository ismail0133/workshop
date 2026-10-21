"""Règle d'alerte par User-Agent et moteur de fenêtres (rejeu ou suivi du fichier).

Un User-Agent déclenche quand `consecutive` fenêtres successives sont à la fois :
  - atypiques (score < seuil du modèle) ;
  - assez fournies (>= min_requests requêtes) : une requête isolée ne justifie jamais un blocage.
Pourquoi 3 et pas 2 : les fenêtres de 10 s glissent de 5 s et se recouvrent de moitié ; un seul pic de
navigation de 3 s remplit donc deux fenêtres successives. Avec 3, la première et la troisième ne se
recouvrent plus : l'activité atypique doit durer au moins ~15 s (constaté sur synthétique puis sur le journal réel).
Après déclenchement il faut `rearm_normal` fenêtres normales (ou absentes) pour pouvoir redéclencher,
et au moins `cooldown_s` secondes. Le déclenchement est idempotent : un même User-Agent n'est signalé
qu'une fois tant qu'il n'est pas revenu à la normale.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field

import numpy as np

from . import STEP_S, WINDOW_S
from .features import MAX_ENTITIES, Step, entities_in_window, first_boundary
from .logs import Request


@dataclass(frozen=True)
class GateParams:
    consecutive: int = 3
    rearm_normal: int = 3
    cooldown_s: float = 60.0
    min_requests: int = 5


@dataclass(frozen=True)
class Trigger:
    ts: float
    ua: str
    n_requests: int
    score: float
    anomalous_windows: int


@dataclass
class _State:
    run: int = 0
    normal_run: int = 0
    triggered: bool = False
    last_trigger: float = -math.inf
    idle: int = 0


@dataclass
class EntityGate:
    params: GateParams = field(default_factory=GateParams)
    states: dict = field(default_factory=dict)

    def step(self, end: float, scored: dict, threshold: float) -> list[Trigger]:
        """`scored` : ua -> (n_requests, score). Retourne les déclenchements de cette fenêtre."""
        p, out = self.params, []
        for ua, (n, sc) in scored.items():
            st = self.states.setdefault(ua, _State())
            st.idle = 0
            if n >= p.min_requests and sc < threshold:
                st.run, st.normal_run = st.run + 1, 0
            else:
                st.run, st.normal_run = 0, st.normal_run + 1
            if st.triggered and st.normal_run >= p.rearm_normal:
                st.triggered = False
            if not st.triggered and st.run >= p.consecutive and end - st.last_trigger >= p.cooldown_s:
                st.triggered, st.last_trigger = True, end
                out.append(Trigger(end, ua, n, sc, st.run))
        for ua in [u for u in self.states if u not in scored]:
            st = self.states[ua]
            st.run, st.normal_run, st.idle = 0, st.normal_run + 1, st.idle + 1
            if st.triggered and st.normal_run >= p.rearm_normal:
                st.triggered = False
            if not st.triggered and st.idle >= 6:  # état oublié : borne la mémoire
                del self.states[ua]
        return out


@dataclass(frozen=True, slots=True)
class ScoredRow:
    end: float
    ua: str
    n: int
    score: float


def score_steps(model, steps: list[Step]) -> list[list[ScoredRow]]:
    """Score toutes les entités de chaque fenêtre (indépendant du seuil)."""
    result: list[list[ScoredRow]] = []
    for step in steps:
        if not step.entities:
            result.append([])
            continue
        uas = list(step.entities)
        scores = model.scores(np.asarray([step.entities[u][1] for u in uas], dtype=float))
        result.append([ScoredRow(step.end, u, step.entities[u][0], float(s)) for u, s in zip(uas, scores, strict=True)])
    return result


def run_gate(scored_steps: list[list[ScoredRow]], steps: list[Step], threshold: float, params: GateParams) -> list[Trigger]:
    gate, triggers = EntityGate(params), []
    for step, rows in zip(steps, scored_steps, strict=True):
        triggers.extend(gate.step(step.end, {r.ua: (r.n, r.score) for r in rows}, threshold))
    return triggers


class StreamEngine:
    """Moteur incrémental : `feed()` ajoute des requêtes, `advance()` ferme les fenêtres terminées.

    Mêmes fenêtres et même règle en rejeu (évaluation) et en suivi du fichier : ce qui est mesuré
    est ce qui tourne.
    """

    def __init__(self, model, params: GateParams | None = None, *, window_s: float = WINDOW_S,
                 step_s: float = STEP_S, lateness_s: float = 1.0, max_entities: int = MAX_ENTITIES):
        self.model, self.params = model, params or GateParams()
        self.window_s, self.step_s, self.lateness_s, self.max_entities = window_s, step_s, lateness_s, max_entities
        self.gate = EntityGate(self.params)
        self._buf: list[Request] = []
        self._next_end: float | None = None
        self.watermark = -math.inf
        self.overflow = 0
        self.rows: list[ScoredRow] = []

    def feed(self, requests) -> None:
        batch = sorted(requests, key=lambda r: r.ts)
        if not batch:
            return
        if self._next_end is None:
            self._next_end = first_boundary(batch[0].ts, self.step_s)
        self._buf = sorted(self._buf + batch, key=lambda r: r.ts)
        self.watermark = max(self.watermark, batch[-1].ts)

    def advance(self, now: float | None = None) -> list[Trigger]:
        if self._next_end is None:
            return []
        horizon = self.watermark if now is None else max(self.watermark, now)
        triggers: list[Trigger] = []
        while self._next_end + self.lateness_s <= horizon:
            if not self._buf and horizon - self._next_end > 10 * self.window_s:  # longue inactivité : on saute
                self._next_end = (math.floor((horizon - 2 * self.window_s) / self.step_s) + 1) * self.step_s
                self.gate.states.clear()
            end = self._next_end
            stamps = [r.ts for r in self._buf]
            lo, hi = bisect_left(stamps, end - self.window_s), bisect_left(stamps, end)
            entities, overflow = entities_in_window(self._buf[lo:hi], self.window_s, self.max_entities)
            self.overflow += overflow
            rows = score_steps(self.model, [Step(end, entities)])[0]
            self.rows.extend(rows)
            triggers.extend(self.gate.step(end, {r.ua: (r.n, r.score) for r in rows}, self.model.threshold))
            self._next_end = end + self.step_s
            self._buf = self._buf[bisect_left(stamps, self._next_end - self.window_s):]
        return triggers


def replay(requests: list[Request], model, params: GateParams | None = None) -> tuple[list[Trigger], StreamEngine]:
    engine = StreamEngine(model, params)
    engine.feed(requests)
    horizon = (engine.watermark + engine.window_s + engine.step_s + engine.lateness_s) if requests else 0.0
    return engine.advance(horizon), engine
