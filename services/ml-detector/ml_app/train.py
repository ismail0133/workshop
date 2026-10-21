"""Entraînement sans fuite : fit sur train normal, seuil sur validation, test gelé."""

from __future__ import annotations

import json
from pathlib import Path

from .dataset import apply_splits, load_dataset
from .evaluate import check_targets, evaluate, render_markdown
from .model import (
    build_pipeline,
    calibrate_threshold,
    frame_to_matrix,
    load_verified,
    save_model,
    score,
)


def train(dataset_dir: Path, out_dir: Path, model_version: str, synthetic: bool) -> dict:
    frame = load_dataset(dataset_dir / "dataset.csv")
    splits = json.loads((dataset_dir / "splits.json").read_text())
    ds_manifest = json.loads((dataset_dir / "manifest.json").read_text())
    parts = apply_splits(frame, splits)
    train_rows = parts["train"]
    if (train_rows["label_degraded"] == 1).any():
        raise ValueError("Le split train doit contenir uniquement du trafic normal")
    if len(train_rows) < 100:
        raise ValueError("Trop peu de points d'entraînement (>= 100 requis)")

    pipeline = build_pipeline(len(train_rows))
    pipeline.fit(frame_to_matrix(train_rows))

    val = parts["validation"]
    normal_val = val[val["label_degraded"] == 0]
    threshold = calibrate_threshold(score(pipeline, frame_to_matrix(normal_val)))

    save_model(
        pipeline,
        out_dir,
        model_version=model_version,
        threshold=threshold,
        dataset_sha256=ds_manifest["dataset_sha256"],
        synthetic=synthetic,
        extra={"n_train": int(len(train_rows)), "n_validation": int(len(val))},
    )
    model = load_verified(out_dir)
    # Le test n'a servi ni au réglage du modèle ni à celui du seuil.
    validation = evaluate(model, val)
    test = evaluate(model, parts["test"])
    report = {
        "validation": validation,
        "test": test,
        "targets_test": check_targets(test),
        "synthetic": synthetic,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    notes = (
        "> ⚠ **Données synthétiques** : test de bout en bout du pipeline, aucune valeur "
        "n'est une performance démontrée sur l'environnement réel."
        if synthetic
        else "Résultats sur données réelles collectées sur le PC Hôte (SC-01)."
    )
    (out_dir / "report.md").write_text(
        render_markdown(
            "Rapport d'entraînement et d'évaluation", model.manifest, validation, test, notes
        )
    )
    return report
