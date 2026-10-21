import httpx
import pytest
from ml_app.features import QUALITY_QUERIES, QUERIES, render
from ml_app.prom import Prometheus, PrometheusError

VALUES = {
    "request_rate": 3.0,
    "http_5xx_rate": 0.0,
    "http_4xx_rate": 0.02,
    "latency_p95_ms": 50.0,
    "cpu_usage_percent": 11.0,
    "memory_usage_percent": 33.0,
    "active_requests": 1.0,
    "payment_failure_rate": 0.0,
}
QUALITY = {"samples": 3, "up": 1, "age_seconds": 1.5, "counter_resets": 0, "payment_attempts": 5}


def fake(values, quality, missing=()):
    table = {render(QUERIES[k], 15): v for k, v in values.items()}
    table.update({render(QUALITY_QUERIES[k], 15): v for k, v in quality.items()})
    skip = {render(QUERIES.get(m) or QUALITY_QUERIES[m], 15) for m in missing}

    def handler(request):
        q = request.url.params["query"]
        if q in skip:
            return httpx.Response(200, json={"status": "success", "data": {"result": []}})
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"result": [{"metric": {}, "value": [1, str(table[q])]}]},
            },
        )

    return Prometheus(
        "http://prom",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://prom"),
    )


def test_extract_valid_window():
    w = fake(VALUES, QUALITY).extract_window(15, at=1000.0)
    assert w.valid and w.start == 985.0 and w.end == 1000.0


def test_absent_series_is_never_treated_as_zero():
    w = fake(VALUES, QUALITY, missing=("http_5xx_rate",)).extract_window(15, at=1000.0)
    assert not w.valid and w.reason == "MISSING_HTTP_5XX_RATE"


def test_missing_up_series_means_target_down():
    w = fake(VALUES, QUALITY, missing=("up",)).extract_window(15, at=1000.0)
    assert not w.valid and w.reason == "TARGET_DOWN"


def test_nan_string_from_prometheus_is_invalid():
    w = fake({**VALUES, "latency_p95_ms": "NaN"}, QUALITY).extract_window(15, at=1000.0)
    assert not w.valid


def test_prometheus_unreachable_raises_controlled_error():
    def boom(request):
        raise httpx.ConnectError("down")

    prom = Prometheus(
        "http://x", client=httpx.Client(transport=httpx.MockTransport(boom), base_url="http://x")
    )
    with pytest.raises(PrometheusError):
        prom.extract_window(15)
