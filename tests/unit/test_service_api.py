"""FastAPI control-plane smoke."""

from fastapi.testclient import TestClient

from service.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_version_gate_endpoint():
    r = client.post(
        "/version-gate",
        json={"n_prev": 100, "s_prev": 82, "n_curr": 100, "s_curr": 50, "eval_delta": -0.2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ci_status"] == "fail"
    assert body["recommended_action"] in ("hold", "rollback")


def test_ingest_ack():
    r = client.post("/ingest")
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"
