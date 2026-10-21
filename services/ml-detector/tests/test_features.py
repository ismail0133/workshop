import math

import pytest
from ml_app.features import (
    FEATURE_NAMES,
    QUALITY_QUERIES,
    QUERIES,
    build_window,
    render,
    validate_quality,
)

GOOD_RAW = dict(
    request_rate=3.0,
    http_5xx_rate=0.0,
    http_4xx_rate=0.02,
    latency_p95_ms=48.0,
    cpu_usage_percent=12.0,
    memory_usage_percent=33.0,
    active_requests=1.2,
    payment_failure_rate=0.0,
)
GOOD_Q = dict(up=1, samples=3, age_seconds=2.0, counter_resets=0, payment_attempts=4)


def test_valid_window_has_ordered_vector():
    w = build_window(0, 15, GOOD_RAW, GOOD_Q)
    assert w.valid and len(w.vector()) == 8
    assert w.vector()[0] == 3.0 and list(w.values) == list(FEATURE_NAMES)


@pytest.mark.parametrize(
    "patch,reason",
    [
        ({"up": 0}, "TARGET_DOWN"),
        ({"up": None}, "TARGET_DOWN"),
        ({"samples": 2}, "TOO_FEW_SAMPLES"),
        ({"age_seconds": 11}, "STALE_SERIES"),
        ({"age_seconds": None}, "STALE_SERIES"),
        ({"counter_resets": 1}, "COUNTER_RESET"),
    ],
)
def test_quality_failures_invalidate_the_window(patch, reason):
    w = build_window(0, 15, GOOD_RAW, {**GOOD_Q, **patch})
    assert not w.valid and w.reason == reason and w.values == {}


def test_no_traffic_is_not_zero_errors():
    w = build_window(0, 15, {**GOOD_RAW, "request_rate": 0.0}, GOOD_Q)
    assert not w.valid and w.reason == "NO_TRAFFIC"


def test_no_payment_attempt_means_failure_rate_unknown():
    w = build_window(0, 15, GOOD_RAW, {**GOOD_Q, "payment_attempts": 0})
    assert not w.valid and w.reason == "NO_PAYMENT_ATTEMPT"


@pytest.mark.parametrize("bad", [None, math.nan, math.inf])
def test_missing_nan_or_inf_feature_invalidates_without_filling(bad):
    w = build_window(0, 15, {**GOOD_RAW, "latency_p95_ms": bad}, GOOD_Q)
    assert not w.valid and w.reason == "MISSING_LATENCY_P95_MS"


def test_values_are_clipped_to_contract_bounds():
    raw = {**GOOD_RAW, "cpu_usage_percent": 180.0, "http_5xx_rate": 1.4, "request_rate": 5.0}
    w = build_window(0, 15, raw, GOOD_Q)
    assert w.values["cpu_usage_percent"] == 100.0 and w.values["http_5xx_rate"] == 1.0


def test_every_feature_has_a_query_and_windows_render():
    assert set(QUERIES) == set(FEATURE_NAMES)
    for q in list(QUERIES.values()) + list(QUALITY_QUERIES.values()):
        assert "{window}" not in render(q, 15)
    assert "[15s]" in render(QUERIES["request_rate"], 15) and "[30s]" in render(
        QUERIES["request_rate"], 30
    )


def test_promql_is_syntactically_valid():
    promql = pytest.importorskip("promql_parser")
    with pytest.raises(BaseException):  # noqa: B017
        promql.parse("sum(rate(x[15s])")  # garde-fou : le parseur rejette bien une syntaxe invalide
    for q in list(QUERIES.values()) + list(QUALITY_QUERIES.values()):
        promql.parse(render(q, 15))


def test_validate_quality_ok():
    assert validate_quality(GOOD_Q) == ""
