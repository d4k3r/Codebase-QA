"""Tests for the currently exposed HTTP API."""

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    # Use the Linux/Uvicorn event-loop backend for reliable TestClient behavior in WSL.
    with TestClient(app, backend_options={"use_uvloop": True}) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
