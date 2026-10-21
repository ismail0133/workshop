"""Livraison au moins une fois vers Incident Service : retries 1/2/4 s puis petite outbox locale.

Le contrat (API_CONTRACTS) : même event_id et même corps à chaque retry ; après épuisement,
conserver l'événement dans une outbox bornée et signaler l'échec ; un événement de plus de 30 s
est archivé et ne déclenche JAMAIS une nouvelle correction (il serait refusé en STALE_EVENT).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

log = logging.getLogger("ml-detector")
RETRY_DELAYS = (1.0, 2.0, 4.0)
STALE_AFTER = 30.0
MAX_OUTBOX = 50


def _age_seconds(event: dict) -> float:
    ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - ts).total_seconds()


class Sender:
    def __init__(
        self,
        url: str | None,
        token: str | None,
        state_dir: Path,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.url, self.token, self.sleep = url, token, sleep
        self.client = client or httpx.Client(timeout=2.0)
        self.state_dir = state_dir
        self.outbox = state_dir / "outbox.jsonl"
        self.archive = state_dir / "archive.jsonl"
        self.failures = 0

    # -- transport -----------------------------------------------------------------------
    def _post(self, event: dict) -> str:
        """Retourne accepted | duplicate | rejected | retry."""
        try:
            response = self.client.post(
                f"{self.url.rstrip('/')}/internal/anomalies",
                json=event,
                headers={"X-Service-Token": self.token or ""},
            )
        except httpx.HTTPError:
            return "retry"
        if response.status_code == 202:
            return "accepted"
        if response.status_code == 200:
            return "duplicate"
        if response.status_code in (429, 503):
            return "retry"
        # 401/403/409/422 : inutile de répéter (REMEDIATION_DESIGN : pas de retry sur validation).
        log.error("anomaly rejected status=%s event_id=%s", response.status_code, event["event_id"])
        return "rejected"

    def send(self, event: dict) -> str:
        if not self.url or not self.token:
            log.warning(
                "dry-run: event_id=%s non envoyé (INCIDENT_URL/token absents)", event["event_id"]
            )
            return "dry-run"
        outcome = self._post(event)
        for delay in RETRY_DELAYS:
            if outcome != "retry":
                break
            self.sleep(delay)
            outcome = self._post(event)
        if outcome == "retry":
            self.failures += 1
            self._enqueue(event)
            return "queued"
        return outcome

    # -- outbox --------------------------------------------------------------------------
    def _enqueue(self, event: dict) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        lines = self.outbox.read_text().splitlines() if self.outbox.exists() else []
        lines.append(json.dumps(event, sort_keys=True))
        self.outbox.write_text("\n".join(lines[-MAX_OUTBOX:]) + "\n")

    def pending(self) -> int:
        return len(self.outbox.read_text().splitlines()) if self.outbox.exists() else 0

    def flush(self) -> dict[str, int]:
        """Rejoue l'outbox : les événements frais repartent ; les périmés sont archivés."""
        stats = {"sent": 0, "archived": 0, "kept": 0}
        if not self.outbox.exists() or not self.url or not self.token:
            return stats
        keep: list[str] = []
        for line in self.outbox.read_text().splitlines():
            event = json.loads(line)
            if _age_seconds(event) > STALE_AFTER:
                with self.archive.open("a") as handle:
                    handle.write(line + "\n")
                stats["archived"] += 1
                continue
            outcome = self._post(event)
            if outcome == "retry":
                keep.append(line)
                stats["kept"] += 1
            else:
                stats["sent"] += 1
        self.outbox.write_text("".join(f"{item}\n" for item in keep))
        return stats
