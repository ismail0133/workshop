"""Générateur de données SYNTHÉTIQUES pour le développement et la CI.

⚠ Ces données ne constituent PAS la preuve du pilier IA : elles servent à tester le pipeline
(collecte → entraînement → évaluation → inférence) avant d'avoir un Prometheus réel. Tout
manifeste produit à partir d'elles porte `synthetic_training_data: true`. Les chiffres du
dossier doivent provenir de `collect` sur le PC Hôte avec le scénario SC-01 réel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import FEATURE_NAMES

STEP = 5  # secondes entre deux points (cadence Prometheus)


def _normal(rng: np.random.Generator, n: int) -> np.ndarray:
    # Client légitime ~1 req/s + utilisateurs ; quelques rafales bénignes sans dégradation.
    rate = np.clip(rng.lognormal(mean=0.4, sigma=0.35, size=n), 0.2, None)
    burst = rng.random(n) < 0.04
    rate[burst] *= rng.uniform(2.0, 4.0, burst.sum())
    p95 = np.clip(rng.lognormal(mean=np.log(45), sigma=0.3, size=n) + rate * 2, 5, None)
    return np.column_stack(
        [
            rate,
            np.clip(rng.normal(0.002, 0.003, n), 0, 1),
            np.clip(rng.normal(0.02, 0.02, n), 0, 1),
            p95,
            np.clip(rng.normal(10 + rate * 3, 4, n), 0, 100),
            np.clip(rng.normal(32, 2.5, n), 0, 100),
            np.clip(rng.normal(0.6 + rate * 0.4, 0.4, n), 0, None),
            np.clip(rng.normal(0.004, 0.006, n), 0, 1),
        ]
    )


def _attack(rng: np.random.Generator, n: int, severity: np.ndarray) -> np.ndarray:
    """SC-01 simulé : charge croissante, p95/5xx/échecs de paiement et CPU qui dérivent."""
    rate = 3 + 45 * severity * rng.uniform(0.7, 1.1, n)
    return np.column_stack(
        [
            rate,
            np.clip(0.30 * severity**1.5 + rng.normal(0, 0.01, n), 0, 1),
            np.clip(rng.normal(0.02, 0.02, n), 0, 1),
            45 + 1400 * severity**1.4 * rng.uniform(0.8, 1.2, n),
            np.clip(10 + 88 * severity + rng.normal(0, 4, n), 0, 100),
            np.clip(rng.normal(36 + 6 * severity, 2.5, n), 0, 100),
            np.clip(1 + 7 * severity + rng.normal(0, 0.5, n), 0, None),
            np.clip(0.45 * severity**1.3 + rng.normal(0, 0.02, n), 0, 1),
        ]
    )


def generate(seed: int = 7) -> tuple[pd.DataFrame, dict]:
    """Trois sessions temporelles disjointes (train 30 min, validation 10 min, test 10 min)."""
    rng = np.random.default_rng(seed)
    frames, splits, clock = [], {"train": [], "validation": [], "test": []}, 1_790_000_000.0
    plan = [
        ("train", "syn-train", 360, []),
        ("validation", "syn-val", 120, [(60, 80)]),
        ("test", "syn-test", 120, [(50, 75), (95, 105)]),
    ]
    for split, run_id, n, attacks in plan:
        data = _normal(rng, n)
        labels = np.zeros(n, dtype=int)
        for start, end in attacks:
            length = end - start
            severity = np.clip(np.linspace(0.25, 1.0, length) ** 0.8, 0, 1)
            data[start:end] = _attack(rng, length, severity)
            labels[start:end] = 1
        times = clock + np.arange(n) * STEP
        frame = pd.DataFrame(data, columns=list(FEATURE_NAMES))
        frame.insert(0, "timestamp", times)
        frame.insert(0, "run_id", run_id)
        frame["label_degraded"] = labels
        frames.append(frame)
        splits[split].append({"run_id": run_id, "from": float(times[0]), "to": float(times[-1])})
        clock = times[-1] + 120  # purge >= 15 s entre sessions (fenêtres chevauchantes)
    return pd.concat(frames, ignore_index=True), splits
