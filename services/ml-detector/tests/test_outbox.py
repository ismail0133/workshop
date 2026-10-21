import json
from datetime import datetime, timedelta, timezone

import httpx
from ml_app.outbox import Sender


def event(age=0.0, i=1):
    ts = (datetime.now(timezone.utc) - timedelta(seconds=age)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {"event_id": f"00000000-0000-4000-8000-00000000000{i}", "timestamp": ts}


def sender(tmp_path, statuses, sleeps=None):
    calls = []
    seq = iter(statuses)

    def handler(request):
        calls.append(request)
        code = next(seq, statuses[-1])
        if code == "boom":
            raise httpx.ConnectError("x")
        return httpx.Response(code)

    return Sender(
        "http://i",
        "t",
        tmp_path,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=(sleeps.append if sleeps is not None else lambda s: None),
    ), calls


def test_accepted_and_duplicate(tmp_path):
    s, calls = sender(tmp_path, [202])
    assert s.send(event()) == "accepted"
    s, _ = sender(tmp_path, [200])
    assert s.send(event()) == "duplicate"


def test_retries_1_2_4_then_queues(tmp_path):
    sleeps = []
    s, calls = sender(tmp_path, [503], sleeps)
    assert s.send(event()) == "queued"
    assert sleeps == [1.0, 2.0, 4.0] and len(calls) == 4 and s.pending() == 1
    assert len({r.content for r in calls}) == 1  # même corps à chaque essai


def test_network_error_is_retried(tmp_path):
    s, calls = sender(tmp_path, ["boom", 202])
    assert s.send(event()) == "accepted" and len(calls) == 2


def test_validation_errors_are_not_retried(tmp_path):
    for code in (401, 403, 409, 422):
        s, calls = sender(tmp_path, [code])
        assert s.send(event()) == "rejected" and len(calls) == 1 and s.pending() == 0


def test_flush_sends_fresh_and_archives_stale(tmp_path):
    s, _ = sender(tmp_path, [503])
    s.send(event(age=1, i=1))
    s._enqueue(event(age=120, i=2))  # périmé : ne doit jamais redéclencher
    s2, calls = sender(tmp_path, [202])
    stats = s2.flush()
    assert stats == {"sent": 1, "archived": 1, "kept": 0} and s2.pending() == 0
    assert json.loads((tmp_path / "archive.jsonl").read_text())["event_id"].endswith("2")
    assert len(calls) == 1


def test_outbox_is_bounded(tmp_path):
    s, _ = sender(tmp_path, [503])
    for i in range(80):
        s._enqueue(event(i=i % 9))
    assert s.pending() == 50
