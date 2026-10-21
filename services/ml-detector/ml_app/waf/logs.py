"""Lecture défensive de `access.jsonl` (format `edge_json` du WAF).

Le fichier contient des données contrôlées par un client (User-Agent, URI) : tout est normalisé,
borné et compté. Une ligne invalide est rejetée avec un code, jamais interprétée.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MAX_LINE_CHARS = 8192
MAX_UA_LEN = 200
MAX_PATH_LEN = 200
NO_UA = "(none)"

_WS = re.compile(r"\s+")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


class LogRejected(ValueError):
    """Ligne rejetée ; `.args[0]` est un code stable (comptabilisé, jamais le contenu)."""


@dataclass(frozen=True, slots=True)
class Request:
    ts: float
    ua: str
    method: str
    path: str
    status: int
    duration_ms: float
    limited: bool
    blocked: bool


def normalise_ua(value: object) -> str:
    text = _WS.sub(" ", _CTRL.sub(" ", str(value))).strip()[:MAX_UA_LEN]
    return text or NO_UA


def _parse_ts(value: object) -> float:
    if not isinstance(value, str):
        raise LogRejected("BAD_TS")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LogRejected("BAD_TS") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def parse_line(line: str) -> Request:
    if len(line) > MAX_LINE_CHARS:
        raise LogRejected("LINE_TOO_LONG")
    try:
        raw = json.loads(line)
    except json.JSONDecodeError as exc:
        raise LogRejected("BAD_JSON") from exc
    if not isinstance(raw, dict):
        raise LogRejected("NOT_AN_OBJECT")
    if raw.get("event") != "HTTP_EDGE":
        raise LogRejected("NOT_EDGE_EVENT")
    ts = _parse_ts(raw.get("ts"))
    status = raw.get("status")
    if isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599:
        raise LogRejected("BAD_STATUS")
    try:
        duration_ms = float(raw.get("duration_s")) * 1000.0
    except (TypeError, ValueError) as exc:
        raise LogRejected("BAD_DURATION") from exc
    if not math.isfinite(duration_ms) or duration_ms < 0:
        raise LogRejected("BAD_DURATION")
    path = str(raw.get("uri", "")).split("?", 1)[0][:MAX_PATH_LEN] or "/"
    return Request(
        ts=ts,
        ua=normalise_ua(raw.get("user_agent", "")),
        method=str(raw.get("method", ""))[:8].upper(),
        path=path,
        status=status,
        duration_ms=duration_ms,
        limited=status == 429 or str(raw.get("limit_req", "PASSED")) not in ("PASSED", "-", ""),
        blocked=str(raw.get("blocked", "0")) == "1",
    )


def read_requests(path: Path) -> tuple[list[Request], dict]:
    """Retourne les requêtes triées par temps et un bilan de lecture (lignes, acceptées, rejets par code)."""
    requests: list[Request] = []
    rejected: Counter[str] = Counter()
    lines = 0
    with Path(path).open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            lines += 1
            try:
                requests.append(parse_line(line))
            except LogRejected as exc:
                rejected[str(exc.args[0])] += 1
    requests.sort(key=lambda r: r.ts)
    return requests, {"lines": lines, "accepted": len(requests), "rejected": dict(rejected)}
