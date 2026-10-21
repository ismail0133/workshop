from fastapi.testclient import TestClient
from ml_app.config import Settings
from ml_app.main import create_app


def cfg(tmp_path, model_dir, pinned=None):
    return Settings("http://prom", None, model_dir, pinned, tmp_path, None, None, 5, 15, 2, 60)


def test_ready_is_503_without_model(tmp_path):
    with TestClient(create_app(cfg(tmp_path, tmp_path / "none"), start_loop=False)) as c:
        assert c.get("/health/live").status_code == 200
        r = c.get("/health/ready")
        assert r.status_code == 503 and r.json()["detail"] == "MODEL_MISSING"


def test_ready_is_503_with_wrong_pinned_hash(tmp_path, trained_dir):
    with TestClient(create_app(cfg(tmp_path, trained_dir, "f" * 64), start_loop=False)) as c:
        assert c.get("/health/ready").json()["detail"] == "PINNED_HASH_MISMATCH"


def test_ready_and_metrics_with_verified_model(tmp_path, trained_dir):
    with TestClient(create_app(cfg(tmp_path, trained_dir), start_loop=False)) as c:
        r = c.get("/health/ready")
        assert r.status_code == 200 and r.json()["model_version"] == "if-test-1"
        text = c.get("/metrics").text
        assert (
            'ml_windows_total{status="invalid"}' in text
            and 'ml_model_info{version="if-test-1"}' in text
        )


def test_no_inference_api_is_exposed(tmp_path, trained_dir):
    with TestClient(create_app(cfg(tmp_path, trained_dir), start_loop=False)) as c:
        for path in ("/predict", "/docs", "/openapi.json", "/api/anything"):
            assert c.get(path).status_code == 404
