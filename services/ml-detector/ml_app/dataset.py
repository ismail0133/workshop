"""Chargement/partition de jeux de données par sessions temporelles (jamais aléatoire)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .features import FEATURE_NAMES

PURGE_SECONDS = 15.0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_dataset(csv_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path)
    required = {"run_id", "timestamp", "label_degraded", *FEATURE_NAMES}
    if missing := required - set(frame.columns):
        raise ValueError(f"Colonnes manquantes : {sorted(missing)}")
    if frame.duplicated(["run_id", "timestamp"]).any():
        raise ValueError("Doublons (run_id, timestamp) interdits")
    return frame.sort_values(["run_id", "timestamp"]).reset_index(drop=True)


def apply_splits(frame: pd.DataFrame, splits: dict) -> dict[str, pd.DataFrame]:
    """Affecte chaque ligne à un split selon des intervalles (run_id, from, to).

    Vérifie qu'aucune session n'appartient à deux splits et que l'espacement entre sessions
    de splits différents dépasse la purge (fenêtre glissante de 15 s).
    """
    out: dict[str, pd.DataFrame] = {}
    seen: dict[str, str] = {}
    for name, ranges in splits.items():
        parts = []
        for item in ranges:
            if item["run_id"] in seen and seen[item["run_id"]] != name:
                raise ValueError(f"Session {item['run_id']} présente dans deux splits")
            seen[item["run_id"]] = name
            mask = (
                (frame["run_id"] == item["run_id"])
                & (frame["timestamp"] >= item["from"])
                & (frame["timestamp"] <= item["to"])
            )
            parts.append(frame[mask])
        out[name] = pd.concat(parts) if parts else frame.iloc[0:0]
    bounds = sorted(
        (item["from"], item["to"], name) for name, ranges in splits.items() for item in ranges
    )
    for (_, end_a, split_a), (start_b, _, split_b) in zip(bounds, bounds[1:], strict=False):
        if split_a != split_b and start_b - end_a < PURGE_SECONDS:
            raise ValueError("Purge insuffisante entre splits (>= 15 s requis)")
    return out


def write_bundle(directory: Path, frame: pd.DataFrame, splits: dict, extra: dict) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / "dataset.csv"
    frame.to_csv(csv_path, index=False)
    (directory / "splits.json").write_text(json.dumps(splits, indent=2))
    manifest = {
        "dataset_sha256": sha256_bytes(csv_path.read_bytes()),
        "rows": int(len(frame)),
        "features": list(FEATURE_NAMES),
        "runs": sorted(frame["run_id"].unique().tolist()),
        **extra,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest
