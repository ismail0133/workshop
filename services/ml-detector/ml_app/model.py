"""Pipeline Isolation Forest, sérialisation vérifiée et calibrage du seuil.

Règles de sécurité (ML_DESIGN) : jamais de joblib/pickle reçu du réseau ; l'artefact est interne
et son SHA-256 est contrôlé avant `joblib.load` contre le manifeste ET, si fourni, contre une
empreinte épinglée dans la configuration (MODEL_SHA256), que le manifeste ne peut pas modifier.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from . import FEATURE_SCHEMA_VERSION
from .features import FEATURE_NAMES, LOG1P_FEATURES

ARTIFACT_NAME = "model.joblib"
MANIFEST_NAME = "manifest.json"
_LOG_IDX = [FEATURE_NAMES.index(n) for n in LOG1P_FEATURES]


class ModelIntegrityError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _log1p_selected(x: np.ndarray) -> np.ndarray:
    x = np.array(x, dtype=float, copy=True)
    x[:, _LOG_IDX] = np.log1p(np.clip(x[:, _LOG_IDX], 0, None))
    return x


def build_pipeline(n_train: int, seed: int = 42) -> Pipeline:
    return Pipeline(
        [
            ("log1p", FunctionTransformer(_log1p_selected, validate=False)),
            ("scale", StandardScaler()),
            (
                "forest",
                IsolationForest(
                    n_estimators=100,
                    max_samples=min(256, n_train),
                    contamination="auto",
                    random_state=seed,
                    n_jobs=1,
                ),
            ),
        ]
    )


def frame_to_matrix(frame: pd.DataFrame) -> np.ndarray:
    missing = [name for name in FEATURE_NAMES if name not in frame.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes : {missing}")
    matrix = frame[list(FEATURE_NAMES)].to_numpy(dtype=float)
    if not np.isfinite(matrix).all():
        raise ValueError("Valeurs NaN/Inf interdites dans le jeu d'entraînement")
    return matrix


def score(pipeline: Pipeline, matrix: np.ndarray) -> np.ndarray:
    """decision_function : plus bas = plus atypique."""
    transformed = pipeline[:-1].transform(matrix)
    return pipeline[-1].decision_function(transformed)


def calibrate_threshold(
    normal_scores: np.ndarray,
    step_seconds: float = 5.0,
    max_fp_per_10min: float = 1.0,
    consecutive: int = 2,
) -> float:
    """Seuil choisi sur la VALIDATION uniquement (jamais sur le test).

    Cible : au plus `max_fp_per_10min` déclenchements (après `consecutive` scores consécutifs
    sous le seuil) sur 10 min de trafic normal. On part du seuil par défaut 0 puis on le
    abaisse jusqu'à satisfaire la cible ; si un seuil strictement positif satisfait déjà la
    contrainte, on conserve 0 (valeur de référence de ML_DESIGN).
    """
    normal_scores = np.asarray(normal_scores, dtype=float)
    periods = (len(normal_scores) * step_seconds / 600.0) or 1.0  # nombre de blocs de 10 min
    candidates = sorted(set(np.round(normal_scores, 6)), reverse=True)

    def triggers(threshold: float) -> int:
        below = normal_scores < threshold
        count, run, armed = 0, 0, True
        for flag in below:
            run = run + 1 if flag else 0
            if run >= consecutive and armed:
                count += 1
                armed = False
            if not flag:
                armed = True
        return count

    if triggers(0.0) / periods <= max_fp_per_10min:
        return 0.0
    for candidate in candidates:
        if candidate < 0 and triggers(candidate) / periods <= max_fp_per_10min:
            return float(candidate)
    return float(min(normal_scores) - 1e-6)


@dataclass
class LoadedModel:
    pipeline: Pipeline
    manifest: dict
    sha256: str

    @property
    def version(self) -> str:
        return self.manifest["model_version"]

    @property
    def threshold(self) -> float:
        return float(self.manifest["threshold"])

    def decision_score(self, vector: list[float]) -> float:
        return float(score(self.pipeline, np.asarray([vector], dtype=float))[0])


def save_model(
    pipeline: Pipeline,
    directory: Path,
    *,
    model_version: str,
    threshold: float,
    dataset_sha256: str,
    synthetic: bool,
    extra: dict | None = None,
) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / ARTIFACT_NAME
    joblib.dump(pipeline, artifact, compress=3)
    manifest = {
        "model_name": "isolation_forest",
        "model_version": model_version,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "features": list(FEATURE_NAMES),
        "threshold": float(threshold),
        "artifact": ARTIFACT_NAME,
        "artifact_sha256": sha256_file(artifact),
        "dataset_sha256": dataset_sha256,
        "synthetic_training_data": bool(synthetic),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "sklearn": sklearn.__version__,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "hyperparameters": {
            "n_estimators": 100,
            "max_samples": pipeline[-1].max_samples,
            "contamination": "auto",
            "random_state": 42,
        },
        **(extra or {}),
    }
    (directory / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def load_verified(directory: Path, pinned_sha256: str | None = None) -> LoadedModel:
    manifest_path, artifact = directory / MANIFEST_NAME, directory / ARTIFACT_NAME
    if not manifest_path.is_file() or not artifact.is_file():
        raise ModelIntegrityError("MODEL_MISSING")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ModelIntegrityError("FEATURE_SCHEMA_MISMATCH")
    if manifest.get("features") != list(FEATURE_NAMES):
        raise ModelIntegrityError("FEATURE_ORDER_MISMATCH")
    actual = sha256_file(artifact)
    if actual != manifest.get("artifact_sha256"):
        raise ModelIntegrityError("MANIFEST_HASH_MISMATCH")
    if pinned_sha256 and actual != pinned_sha256.lower():
        raise ModelIntegrityError("PINNED_HASH_MISMATCH")
    if manifest.get("sklearn") != sklearn.__version__:
        raise ModelIntegrityError("SKLEARN_VERSION_MISMATCH")
    return LoadedModel(joblib.load(artifact), manifest, actual)  # hash vérifié juste avant
