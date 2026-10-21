import json
import uuid
from datetime import datetime, timezone

import httpx
import jsonschema
from conftest import SCHEMA
from ml_app.config import Settings
from ml_app.detector import Detector, build_event
from ml_app.features import FEATURE_NAMES, FeatureWindow
from ml_app.metrics import Metrics
from ml_app.outbox import Sender
from ml_app.prom import PrometheusError

ATTACK = dict(
    request_rate=40.0,
    http_5xx_rate=0.25,
    http_4xx_rate=0.02,
    latency_p95_ms=1200.0,
    cpu_usage_percent=95.0,
    memory_usage_percent=40.0,
    active_requests=7.0,
    payment_failure_rate=0.4,
)
NORMAL = dict(
    request_rate=3.0,
    http_5xx_rate=0.002,
    http_4xx_rate=0.02,
    latency_p95_ms=50.0,
    cpu_usage_percent=12.0,
    memory_usage_percent=32.0,
    active_requests=1.0,
    payment_failure_rate=0.004,
)


class FakeProm:
    def __init__(self, script):
        self.script = list(script)

    def extract_window(self, window_seconds=15, at=None):
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        end = at or 1000.0
        if isinstance(item, str):
            return FeatureWindow(end - 15, end, {}, False, item)
        return FeatureWindow(end - 15, end, dict(item), True)


def settings(tmp_path):
    return Settings(
        prometheus_url="x",
        incident_url="http://incident:8002",
        model_dir=tmp_path,
        pinned_sha256=None,
        state_dir=tmp_path,
        log_dir=None,
        anomaly_token="tok",
        interval_seconds=5,
        window_seconds=15,
        consecutive=2,
        cooldown_seconds=60,
    )


def make(model, tmp_path, script, status=202):
    sent = []

    def handler(request):
        sent.append((request.headers.get("x-service-token"), json.loads(request.content)))
        return httpx.Response(status)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    sender = Sender("http://incident:8002", "tok", tmp_path, client=client, sleep=lambda s: None)
    return Detector(model, FakeProm(script), sender, Metrics(), settings(tmp_path)), sent


def test_two_consecutive_anomalies_emit_one_schema_valid_event(model, tmp_path):
    det, sent = make(model, tmp_path, [NORMAL, ATTACK, ATTACK, ATTACK, ATTACK])
    emitted = [det.tick(at=1000.0 + 5 * i) for i in range(5)]
    assert [e is not None for e in emitted] == [False, False, True, False, False]
    token, body = sent[0]
    assert token == "tok" and len(sent) == 1
    jsonschema.validate(body, json.loads(SCHEMA.read_text()))
    assert body["model"]["artifact_sha256"] == model.sha256 and body["model"]["is_anomaly"] is True
    assert "source_ip" not in json.dumps(body)
    assert set(body["features"]) == set(FEATURE_NAMES)
    ts = datetime.fromisoformat(body["timestamp"].replace("Z", "+00:00"))
    we = datetime.fromisoformat(body["window_end"].replace("Z", "+00:00"))
    assert we <= ts and ts.tzinfo == timezone.utc


def test_single_spike_never_triggers(model, tmp_path):
    det, sent = make(model, tmp_path, [NORMAL, ATTACK, NORMAL, ATTACK, NORMAL])
    assert all(det.tick(at=1000.0 + 5 * i) is None for i in range(5)) and not sent


def test_invalid_window_neither_infers_nor_triggers_and_breaks_the_run(model, tmp_path):
    det, sent = make(
        model, tmp_path, [ATTACK, "STALE_SERIES", ATTACK, PrometheusError("Timeout"), ATTACK]
    )
    assert all(det.tick(at=1000.0 + 5 * i) is None for i in range(5)) and not sent
    assert det.last_error == ""  # dernière fenêtre valide : l'erreur est effacée
    assert det.metrics.windows.labels("invalid")._value.get() == 2


def test_event_id_is_deterministic_for_idempotent_retries(model):
    w = FeatureWindow(985.0, 1000.0, dict(ATTACK), True)
    a, b = build_event(model, w, -0.2, 1001.0), build_event(model, w, -0.2, 1003.0)
    assert a["event_id"] == b["event_id"] and uuid.UUID(a["event_id"]).version == 5


def test_dry_run_without_incident_url(model, tmp_path):
    s = Sender(None, None, tmp_path)
    assert s.send({"event_id": "x"}) == "dry-run"
