"""Journaux WAF synthétiques pour les tests (format edge_json réel, trafic reproductible)."""

import json
import random
from datetime import datetime, timezone

BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
FLOOD = "TestFlood/1.0"
BASE = 1_760_000_000  # multiple de 5 : fenêtres alignées


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def line(ts, ua=BROWSER, uri="/", status=200, duration="0.020", method="GET", **extra) -> str:
    record = {
        "ts": iso(ts), "service": "waf", "event": "HTTP_EDGE", "request_id": "r", "backend_request_id": "b",
        "client_ip": "172.24.0.1", "method": method, "uri": uri, "status": status, "bytes_out": 100, "bytes_in": 10,
        "duration_s": duration, "upstream": "x", "upstream_status": str(status), "upstream_duration_s": duration,
        "blocked": "0", "limit_req": "PASSED", "scheme": "http", "user_agent": ua,
    }
    record.update(extra)
    return json.dumps(record)


URIS = ["/", "/api/accounts", "/api/payments", "/status/payment", "/assets/app.js", "/favicon.ico"]


def normal_lines(start, end, seed=1, page_every=25):
    """Navigation : filet de requêtes + chargements de page (rafales de 6 à 14 requêtes sur 3 s)."""
    rng, out, t = random.Random(seed), [], start
    while t < end:
        for k in range(rng.randint(6, 14)):
            out.append((t + k * 0.25, line(t + k * 0.25, uri=rng.choice(URIS), duration=f"{rng.uniform(0.01, 0.6):.3f}",
                                             method="POST" if rng.random() < 0.1 else "GET")))
        t += rng.uniform(page_every * 0.6, page_every * 1.4)
        for _ in range(rng.randint(0, 2)):
            out.append((t, line(t, uri=rng.choice(URIS), duration=f"{rng.uniform(0.01, 0.3):.3f}")))
            t += rng.uniform(2, 6)
    return out


def flood_lines(start, end, rate=70, ua=FLOOD, uri="/"):
    n = int((end - start) * rate)
    return [(start + i / rate, line(start + i / rate, ua=ua, uri=uri, duration="0.001")) for i in range(n)]


def write_log(path, *parts):
    rows = sorted((r for part in parts for r in part), key=lambda x: x[0])
    path.write_text("\n".join(row for _, row in rows) + "\n", encoding="utf-8")


def standard_log(path, seed=1):
    """train 12 min normal | validation: flood + normal | test: flood + normal. Retourne le dict de séparation."""
    t0 = BASE
    spans = {
        "train": (t0, t0 + 720),
        "val_flood": (t0 + 780, t0 + 840),
        "val_normal": (t0 + 900, t0 + 1100),
        "test_flood": (t0 + 1160, t0 + 1220),
        "test_normal": (t0 + 1280, t0 + 1500),
    }
    write_log(
        path,
        normal_lines(spans["train"][0], spans["train"][1], seed),
        flood_lines(*spans["val_flood"]),
        normal_lines(spans["val_normal"][0], spans["val_normal"][1], seed + 1),
        flood_lines(*spans["test_flood"]),
        normal_lines(spans["test_normal"][0], spans["test_normal"][1], seed + 2),
    )
    return {
        "attack_marker": "TestFlood", "window_s": 10, "step_s": 5, "consecutive": 3, "min_requests": 5,
        "splits": {
            "train": [[iso(spans["train"][0]), iso(spans["train"][1])]],
            "validation": [[iso(spans["val_flood"][0] - 20), iso(spans["val_flood"][1] + 20)],
                           [iso(spans["val_normal"][0]), iso(spans["val_normal"][1])]],
            "test": [[iso(spans["test_flood"][0] - 20), iso(spans["test_flood"][1] + 20)],
                     [iso(spans["test_normal"][0]), iso(spans["test_normal"][1])]],
        },
    }
