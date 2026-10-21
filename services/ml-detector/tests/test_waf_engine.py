import numpy as np
from ml_app.waf.engine import EntityGate, GateParams, StreamEngine, replay
from ml_app.waf.features import FEATURE_NAMES
from ml_app.waf.logs import parse_line
from waf_support import BASE, BROWSER, FLOOD, flood_lines, line, normal_lines

RATE = FEATURE_NAMES.index("req_per_s")


class StubModel:
    """Atypique (score -1) dès que le débit dépasse 2 req/s ; sinon normal (+1)."""

    threshold = 0.0

    def scores(self, matrix):
        return np.where(np.asarray(matrix)[:, RATE] > 2.0, -1.0, 1.0)


def reqs(rows):
    return [parse_line(r) for _, r in sorted(rows)]


def test_gate_needs_consecutive_anomalous_windows_and_enough_requests():
    g = EntityGate(GateParams(consecutive=2, min_requests=5))
    assert g.step(5, {"a": (50, -1.0)}, 0.0) == []                      # 1re fenêtre : pas encore
    assert [t.ua for t in g.step(10, {"a": (50, -1.0)}, 0.0)] == ["a"]  # 2e : déclenche
    assert g.step(15, {"a": (50, -1.0)}, 0.0) == []                     # idempotent
    h = EntityGate(GateParams(consecutive=2, min_requests=5))
    assert h.step(5, {"a": (2, -1.0)}, 0.0) == [] and h.step(10, {"a": (2, -1.0)}, 0.0) == []  # trop peu de requêtes


def test_isolated_spike_does_not_trigger_and_resets_the_run():
    g = EntityGate(GateParams(consecutive=2))
    seq = [(-1.0, 50), (1.0, 50), (-1.0, 50), (1.0, 50), (-1.0, 50)]
    assert all(g.step(5 * i, {"a": (n, s)}, 0.0) == [] for i, (s, n) in enumerate(seq))


def test_rearm_needs_normal_windows_and_respects_cooldown():
    g = EntityGate(GateParams(consecutive=1, rearm_normal=2, cooldown_s=30))
    assert len(g.step(0, {"a": (50, -1)}, 0.0)) == 1
    assert g.step(5, {"a": (50, -1)}, 0.0) == []
    g.step(10, {}, 0.0)
    g.step(15, {}, 0.0)                                  # deux fenêtres absentes : réarmé
    assert g.step(20, {"a": (50, -1)}, 0.0) == []        # mais cooldown (30 s) non écoulé
    assert len(g.step(40, {"a": (50, -1)}, 0.0)) == 1


def test_gate_forgets_idle_entities_to_bound_memory():
    g = EntityGate()
    for i in range(50):
        g.step(5 * i, {f"ua{i}": (1, 1.0)}, 0.0)
    assert len(g.states) < 10


def test_flood_is_detected_in_two_windows_and_browser_is_not_blamed():
    rows = normal_lines(BASE, BASE + 200, seed=3) + flood_lines(BASE + 60, BASE + 120)
    triggers, engine = replay(reqs(rows), StubModel(), GateParams())
    flood = [t for t in triggers if t.ua == FLOOD]
    assert len(flood) == 1 and 60 < flood[0].ts - BASE <= 90
    assert not [t for t in triggers if t.ua == BROWSER]
    assert engine.rows  # fenêtres scorées conservées pour l'évaluation


def test_user_agent_rotation_evades_detection_documented_limit():
    rows = [(BASE + i / 70, line(BASE + i / 70, ua=f"Bot{i}/1.0", uri="/", duration="0.001")) for i in range(70 * 60)]
    triggers, _ = replay(reqs(rows), StubModel(), GateParams())
    assert triggers == []  # LIMITE : 4200 identités à une requête chacune, aucune n'est « fournie »


def test_streaming_in_chunks_gives_the_same_triggers_as_batch_replay():
    data = reqs(normal_lines(BASE, BASE + 200, seed=4) + flood_lines(BASE + 60, BASE + 120))
    batch, _ = replay(data, StubModel(), GateParams())
    engine, streamed = StreamEngine(StubModel(), GateParams()), []
    for i in range(0, len(data), 137):
        engine.feed(data[i : i + 137])
        streamed.extend(engine.advance())
    streamed.extend(engine.advance(data[-1].ts + 60))
    assert [(t.ua, t.ts) for t in streamed] == [(t.ua, t.ts) for t in batch]


def test_long_silence_does_not_loop_over_every_empty_window():
    engine = StreamEngine(StubModel(), GateParams())
    engine.feed(reqs(flood_lines(BASE, BASE + 30)))
    engine.advance(BASE + 40)
    engine.advance(BASE + 10 * 24 * 3600)  # dix jours plus tard
    assert engine._next_end > BASE + 9 * 24 * 3600
    assert engine.gate.states == {}


def test_one_short_normal_burst_cannot_trigger_with_the_default_gate():
    """Un pic de 3 s (12 requêtes) remplit 2 fenêtres glissantes successives, jamais 3."""
    burst = [(BASE + 100 + k * 0.25, line(BASE + 100 + k * 0.25, uri=f"/u{k}")) for k in range(12)]
    heavy = StubModel()
    heavy.scores = lambda m: np.full(len(m), -1.0)  # pire cas : toute fenêtre est jugée atypique
    triggers, engine = replay(reqs(burst), heavy, GateParams())
    assert triggers == []
    assert max(len([r for r in engine.rows if r.end == e]) for e in {r.end for r in engine.rows}) == 1
    assert GateParams().consecutive == 3
