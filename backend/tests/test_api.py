"""Tests for endpoint schemas and thin route behavior."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.database import get_db
from app.main import app
from app.services.retrieval import RetrievedChunk
from app.services.rag import LLMConfigurationError, RAGGenerationError
from app.services.retrieval import RetrievalError
from app.services.chunker import SourceReadError
from app.services.repository_loader import RepositoryReadError
from app.services.storage import IndexingStats, StorageError


def _fake_db() -> Any:
    yield object()


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app, backend_options={"use_uvloop": True}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_index_endpoint_returns_statistics(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes,
        "index_repository",
        lambda db, path, name: IndexingStats(name, 3, 4, 4),
    )

    response = client.post(
        "/repositories/index",
        json={"repository_path": "/tmp/example", "repository_name": "tiny-repo"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "repository": "tiny-repo",
        "python_files_discovered": 3,
        "chunks_created": 4,
        "rows_stored": 4,
    }


def test_search_endpoint_returns_source_metadata(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = RetrievedChunk(
        repository="tiny-repo",
        file_path="calculator.py",
        symbol_type="function",
        symbol_name="add",
        start_line=4,
        end_line=6,
        content="def add(left, right):\n    return left + right\n",
        cosine_distance=0.125,
    )
    monkeypatch.setattr(routes, "search_code", lambda db, query, top_k: [result])

    response = client.post("/search", json={"query": "add two numbers", "top_k": 1})

    assert response.status_code == 200
    assert response.json()["results"][0]["cosine_distance"] == 0.125
    assert response.json()["results"][0]["symbol_name"] == "add"


def test_search_schema_rejects_invalid_top_k(client: TestClient) -> None:
    response = client.post("/search", json={"query": "anything", "top_k": 0})

    assert response.status_code == 422


def test_ask_reports_missing_llm_configuration(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_without_config(*args: object) -> None:
        raise LLMConfigurationError("Missing required LLM configuration: LLM_API_KEY")

    monkeypatch.setattr(routes, "answer_question", fail_without_config)

    response = client.post("/ask", json={"question": "How does addition work?"})

    assert response.status_code == 503
    assert "LLM_API_KEY" in response.json()["detail"]


def test_index_hides_internal_failure_details(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        routes,
        "index_repository",
        lambda *args: (_ for _ in ()).throw(StorageError("password=synthetic-secret")),
    )

    response = client.post(
        "/repositories/index",
        json={"repository_path": "/tmp/example", "repository_name": "tiny-repo"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Repository indexing failed."
    assert "synthetic-secret" not in response.text
    assert "synthetic-secret" not in caplog.text


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (
            RepositoryReadError("/sensitive/repository synthetic-permission-detail"),
            "Could not safely read the repository directories.",
        ),
        (
            SourceReadError("/sensitive/source.py synthetic-read-detail"),
            "Could not safely read the repository source files.",
        ),
    ],
)
def test_index_hides_filesystem_diagnostics(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    detail: str,
) -> None:
    monkeypatch.setattr(
        routes,
        "index_repository",
        lambda *args: (_ for _ in ()).throw(error),
    )

    response = client.post(
        "/repositories/index",
        json={"repository_path": "/tmp/example", "repository_name": "tiny-repo"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == detail
    assert "synthetic" not in response.text


def test_search_hides_internal_failure_details(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes,
        "search_code",
        lambda *args: (_ for _ in ()).throw(RetrievalError("connection secret=synthetic")),
    )

    response = client.post("/search", json={"query": "anything"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Semantic search failed."
    assert "synthetic" not in response.text


def test_ask_hides_internal_failure_details(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes,
        "answer_question",
        lambda *args: (_ for _ in ()).throw(RAGGenerationError("provider secret=synthetic")),
    )

    response = client.post("/ask", json={"question": "anything"})

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM generation failed."
    assert "synthetic" not in response.text
