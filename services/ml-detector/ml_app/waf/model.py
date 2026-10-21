"""Modèle du détecteur WAF : Isolation Forest sur 7 caractéristiques, artefact vérifié.

Même discipline que le détecteur Prometheus : le joblib n'est chargé qu'après contrôle de son SHA-256
(manifeste, et empreinte épinglée si fournie) et de la version de scikit-learn.
"""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from ..model import ARTIFACT_NAME, MANIFEST_NAME, ModelIntegrityError, sha256_file
from . import STEP_S, WAF_SCHEMA_VERSION, WINDOW_S
from .features import FEATURE_NAMES, LOG1P_FEATURES

_LOG_IDX = [FEATURE_NAMES.index(name) for name in LOG1P_FEATURES]


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
                    n_estimators=200,
                    max_samples=min(256, n_train),
                    contamination="auto",
                    random_state=seed,
                    n_jobs=1,
                ),
            ),
        ]
    )


def score(pipeline: Pipeline, matrix: np.ndarray) -> np.ndarray:
    """decision_function : plus bas = plus atypique."""
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != len(FEATURE_NAMES) or not np.isfinite(matrix).all():
        raise ValueError("matrice de caractéristiques invalide")
    return pipeline[-1].decision_function(pipeline[:-1].transform(matrix))


@dataclass
class LoadedWafModel:
    pipeline: Pipeline
    manifest: dict
    sha256: str

    @property
    def version(self) -> str:
        return self.manifest["model_version"]

    @property
    def threshold(self) -> float:
        return float(self.manifest["threshold"])

    @property
    def normal_user_agents(self) -> list[str]:
        return list(self.manifest.get("normal_user_agents", []))

    def scores(self, matrix) -> np.ndarray:
        return score(self.pipeline, np.asarray(matrix, dtype=float))


def save_model(
    pipeline: Pipeline,
    directory: Path,
    *,
    model_version: str,
    threshold: float,
    dataset_sha256: str,
    normal_user_agents: list[str],
    gate: dict,
    extra: dict | None = None,
) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / ARTIFACT_NAME
    joblib.dump(pipeline, artifact, compress=3)
    manifest = {
        "model_name": "isolation_forest_waf_user_agent",
        "model_version": model_version,
        "feature_schema_version": WAF_SCHEMA_VERSION,
        "features": list(FEATURE_NAMES),
        "window_s": WINDOW_S,
        "step_s": STEP_S,
        "threshold": float(threshold),
        "gate": gate,
        "normal_user_agents": normal_user_agents,
        "artifact": ARTIFACT_NAME,
        "artifact_sha256": sha256_file(artifact),
        "dataset_sha256": dataset_sha256,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "sklearn": sklearn.__version__,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "hyperparameters": {
            "n_estimators": 200,
            "max_samples": pipeline[-1].max_samples,
            "contamination": "auto",
            "random_state": 42,
        },
        **(extra or {}),
    }
    (directory / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def load_verified(directory: Path, pinned_sha256: str | None = None) -> LoadedWafModel:
    manifest_path, artifact = directory / MANIFEST_NAME, directory / ARTIFACT_NAME
    if not manifest_path.is_file() or not artifact.is_file():
        raise ModelIntegrityError("MODEL_MISSING")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("feature_schema_version") != WAF_SCHEMA_VERSION:
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
    return LoadedWafModel(joblib.load(artifact), manifest, actual)  # hash vérifié juste avant
