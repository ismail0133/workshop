"""Client Prometheus minimal (requêtes instantanées, timeout 2 s)."""

from __future__ import annotations

import time

import httpx

from .features import QUALITY_QUERIES, QUERIES, FeatureWindow, build_window, render


class PrometheusError(RuntimeError):
    pass


class Prometheus:
    def __init__(self, base_url: str, timeout: float = 2.0, client: httpx.Client | None = None):
        self.client = client or httpx.Client(base_url=base_url, timeout=timeout)

    def scalar(self, query: str, at: float | None = None) -> float | None:
        params = {"query": query}
        if at is not None:
            params["time"] = f"{at:.3f}"
        try:
            response = self.client.get("/api/v1/query", params=params)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PrometheusError(type(exc).__name__) from None
        if body.get("status") != "success":
            raise PrometheusError("QUERY_FAILED")
        result = body["data"]["result"]
        if not result:
            return None  # série absente : jamais assimilée à zéro
        try:
            return float(result[0]["value"][1])
        except (KeyError, IndexError, ValueError, TypeError):
            return None

    def extract_window(self, window_seconds: int = 15, at: float | None = None) -> FeatureWindow:
        end = at if at is not None else time.time()
        raw = {
            name: self.scalar(render(query, window_seconds), at) for name, query in QUERIES.items()
        }
        quality = {
            name: self.scalar(render(query, window_seconds), at)
            for name, query in QUALITY_QUERIES.items()
        }
        return build_window(end - window_seconds, end, raw, quality)
