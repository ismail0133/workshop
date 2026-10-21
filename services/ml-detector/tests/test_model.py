import json

import numpy as np
import pytest
from ml_app.dataset import apply_splits
from ml_app.model import ModelIntegrityError, calibrate_threshold, load_verified


def test_manifest_records_provenance(trained_dir):
    m = json.loads((trained_dir / "manifest.json").read_text())
    assert m["synthetic_training_data"] is True and len(m["artifact_sha256"]) == 64
    assert (
        m["hyperparameters"]["n_estimators"] == 100 and m["hyperparameters"]["random_state"] == 42
    )
    assert m["features"][0] == "request_rate" and m["feature_schema_version"] == "fs-1"


def test_normal_scores_higher_than_degraded(model):
    normal = [3.0, 0.002, 0.02, 50.0, 12.0, 32.0, 1.0, 0.004]
    attack = [40.0, 0.25, 0.02, 1200.0, 95.0, 40.0, 7.0, 0.4]
    assert model.decision_score(attack) < model.threshold
    assert (
        model.decision_score(normal) >= model.threshold - 0.05
    )  # une charge normale n'est pas flaggée
    assert model.decision_score(attack) < model.decision_score(normal)


def test_tampered_artifact_is_refused(trained_dir, tmp_path):
    import shutil

    copy = tmp_path / "m"
    shutil.copytree(trained_dir, copy)
    with (copy / "model.joblib").open("ab") as handle:
        handle.write(b"\x00")
    with pytest.raises(ModelIntegrityError, match="MANIFEST_HASH_MISMATCH"):
        load_verified(copy)


def test_manifest_cannot_vouch_for_itself_when_hash_is_pinned(trained_dir):
    with pytest.raises(ModelIntegrityError, match="PINNED_HASH_MISMATCH"):
        load_verified(trained_dir, "0" * 64)
    ok = json.loads((trained_dir / "manifest.json").read_text())["artifact_sha256"]
    assert load_verified(trained_dir, ok.upper()).sha256 == ok


def test_feature_order_or_schema_change_is_refused(trained_dir, tmp_path):
    import shutil

    copy = tmp_path / "m"
    shutil.copytree(trained_dir, copy)
    manifest = json.loads((copy / "manifest.json").read_text())
    manifest["features"] = manifest["features"][::-1]
    (copy / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ModelIntegrityError, match="FEATURE_ORDER_MISMATCH"):
        load_verified(copy)


def test_missing_model_is_reported(tmp_path):
    with pytest.raises(ModelIntegrityError, match="MODEL_MISSING"):
        load_verified(tmp_path)


def test_threshold_is_calibrated_on_validation_target():
    rng = np.random.default_rng(0)
    scores = rng.normal(0.1, 0.05, 600)
    thr = calibrate_threshold(scores)
    below = scores < thr
    triggers = sum(
        1
        for i in range(1, len(below))
        if below[i] and below[i - 1] and not (i > 1 and below[i - 2])
    )
    assert triggers <= 600 * 5 / 600  # <= 1 déclenchement / 10 min


def test_splits_reject_leakage_and_missing_purge(synthetic_bundle):
    from ml_app.dataset import load_dataset

    frame = load_dataset(synthetic_bundle / "dataset.csv")
    t0 = float(frame[frame.run_id == "syn-train"].timestamp.max())
    with pytest.raises(ValueError, match="deux splits"):
        apply_splits(
            frame,
            {
                "train": [{"run_id": "syn-train", "from": 0, "to": 9e12}],
                "test": [{"run_id": "syn-train", "from": 0, "to": 9e12}],
            },
        )
    with pytest.raises(ValueError, match="Purge"):
        apply_splits(
            frame,
            {
                "train": [{"run_id": "a", "from": 0, "to": t0}],
                "test": [{"run_id": "b", "from": t0 + 5, "to": t0 + 100}],
            },
        )


def test_training_refuses_attack_rows_in_train(synthetic_bundle, tmp_path):
    import shutil

    import pandas as pd
    from ml_app.train import train

    d = tmp_path / "ds"
    shutil.copytree(synthetic_bundle, d)
    frame = pd.read_csv(d / "dataset.csv")
    frame.loc[frame.run_id == "syn-train", "label_degraded"] = 1
    frame.to_csv(d / "dataset.csv", index=False)
    with pytest.raises(ValueError, match="uniquement du trafic normal"):
        train(d, tmp_path / "out", "x", True)
