import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SCHEMA = ROOT.parents[1] / "docs" / "api" / "events.schema.json"


@pytest.fixture(scope="session")
def synthetic_bundle(tmp_path_factory):
    from ml_app.dataset import write_bundle
    from ml_app.synthetic import generate

    frame, splits = generate(7)
    directory = tmp_path_factory.mktemp("synthetic")
    write_bundle(directory, frame, splits, {"synthetic": True})
    return directory


@pytest.fixture(scope="session")
def trained_dir(synthetic_bundle, tmp_path_factory):
    from ml_app.train import train

    out = tmp_path_factory.mktemp("model")
    train(synthetic_bundle, out, "if-test-1", synthetic=True)
    return out


@pytest.fixture
def model(trained_dir):
    from ml_app.model import load_verified

    return load_verified(trained_dir)
