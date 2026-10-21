from ml_app.evaluate import _ratio, evaluate
from ml_app.gate import AlertGate


def drive(gate, flags, step=5.0, t0=0.0):
    return [gate.update(f, t0 + i * step) for i, f in enumerate(flags)]


def test_needs_two_consecutive_anomalies():
    assert drive(AlertGate(), [1, 0, 1, 0, 1, 0]) == [False] * 6
    assert drive(AlertGate(), [1, 1]) == [False, True]


def test_single_alert_per_episode_then_rearm_after_cooldown():
    g = AlertGate(cooldown_s=60)
    assert sum(drive(g, [1] * 30)) == 1  # dédup pendant l'épisode
    drive(g, [0] * 4, t0=1000)  # 3 normales + cooldown écoulé
    assert sum(drive(g, [1, 1], t0=1100)) == 1  # nouvelle alerte possible


def test_cooldown_blocks_fast_retrigger():
    g = AlertGate(cooldown_s=60)
    drive(g, [1, 1])
    drive(g, [0, 0, 0], t0=10)  # normal mais < 60 s
    assert sum(drive(g, [1, 1], t0=25)) == 0


def test_invalid_window_breaks_the_run():
    g = AlertGate()
    g.update(True, 0)
    g.reset_run()  # fenêtre DATA_UNAVAILABLE
    assert g.update(True, 10) is False and g.update(True, 15) is True


def test_ratio_is_explicitly_undefined_on_zero_denominator():
    assert _ratio(0, 0) is None and _ratio(1, 2) == 0.5


def test_evaluate_on_frozen_test(model, synthetic_bundle):
    import json

    from ml_app.dataset import apply_splits, load_dataset

    frame = load_dataset(synthetic_bundle / "dataset.csv")
    test = apply_splits(frame, json.loads((synthetic_bundle / "splits.json").read_text()))["test"]
    res = evaluate(model, test)
    c = res["confusion"]
    assert c["TP"] + c["FN"] == res["n_degraded"] and sum(c.values()) == res["n_windows"]
    assert res["episodes"] == 2 and res["recall"] > 0.8
    assert res["detection_latency_s"]["n"] == res["episodes"] - res["episodes_missed"]


def test_evaluate_without_positive_class_gives_undefined_metrics(model, synthetic_bundle):
    import json

    from ml_app.dataset import apply_splits, load_dataset

    frame = load_dataset(synthetic_bundle / "dataset.csv")
    train = apply_splits(frame, json.loads((synthetic_bundle / "splits.json").read_text()))["train"]
    res = evaluate(model, train)
    assert res["recall"] is None and res["precision"] in (None, 0.0)
    assert res["detection_latency_s"]["p95"] is None
