from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    # Subset assertion: SPEC 2 adds a "demo_mode" key to this payload.
    assert response.json()["status"] == "ok"


def test_health_does_not_touch_the_database(monkeypatch):
    """Liveness must stay green while Postgres is briefly unavailable."""
    from app.api.routes import health as health_route

    def explode(*args, **kwargs):
        raise AssertionError("liveness must not query the database")

    monkeypatch.setattr(health_route, "check_database", explode)
    assert client.get("/health").status_code == 200


def test_ready_reports_database_reachability():
    response = client.get("/ready")
    assert response.status_code in (200, 503)
    assert "database" in response.json()
