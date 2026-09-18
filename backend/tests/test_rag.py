"""Tests for visible, bounded RAG prompt construction and configuration errors."""

from types import SimpleNamespace

import pytest

from app.services import rag
from app.services.retrieval import RetrievedChunk


def test_build_context_includes_source_metadata() -> None:
    source = RetrievedChunk(
        repository="tiny-repo",
        file_path="calculator.py",
        symbol_type="function",
        symbol_name="add",
        start_line=4,
        end_line=6,
        content="return left + right",
        cosine_distance=0.1,
    )

    context = rag.build_context([source])

    assert "tiny-repo/calculator.py" in context.text
    assert "lines 4-6" in context.text
    assert "return left + right" in context.text
    assert len(context.text) <= rag.MAX_CONTEXT_CHARACTERS
    assert context.included_chunks == [source]


def test_build_context_enforces_bound_across_multiple_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rag, "MAX_CONTEXT_CHARACTERS", 300)
    large_source = RetrievedChunk(
        repository="tiny-repo",
        file_path="large.py",
        symbol_type="module",
        symbol_name=None,
        start_line=1,
        end_line=100,
        content="x" * 500,
        cosine_distance=0.2,
    )
    small_source = RetrievedChunk(
        repository="tiny-repo",
        file_path="small.py",
        symbol_type="function",
        symbol_name="small",
        start_line=1,
        end_line=2,
        content="return 1",
        cosine_distance=0.3,
    )

    context = rag.build_context([large_source, small_source])

    assert len(context.text) <= 300
    assert large_source not in context.included_chunks
    assert context.included_chunks == [small_source]
    assert "large.py" not in context.text


def test_missing_llm_configuration_fails_before_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        llm_api_key=None,
        llm_model_name=None,
        llm_base_url=None,
    )
    monkeypatch.setattr(rag, "get_settings", lambda: settings)
    monkeypatch.setattr(
        rag,
        "search_code",
        lambda *args: pytest.fail("retrieval should not run without LLM configuration"),
    )

    with pytest.raises(rag.LLMConfigurationError, match="LLM_API_KEY, LLM_MODEL_NAME"):
        rag.answer_question(object(), "How is addition implemented?")  # type: ignore[arg-type]


def test_answer_question_sends_grounded_prompt_and_returns_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = RetrievedChunk(
        repository="tiny-repo",
        file_path="calculator.py",
        symbol_type="function",
        symbol_name="add",
        start_line=4,
        end_line=6,
        content="return left + right",
        cosine_distance=0.1,
    )
    settings = SimpleNamespace(
        llm_api_key="test-key",
        llm_model_name="test-model",
        llm_base_url="http://localhost:9999/v1",
    )
    captured: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            message = SimpleNamespace(content="Addition returns left + right.")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions()),
        close=lambda: captured.update(client_closed=True),
    )
    fake_db = SimpleNamespace(rollback=lambda: captured.update(rolled_back=True))
    monkeypatch.setattr(rag, "get_settings", lambda: settings)
    def fake_search(
        db: object,
        question: str,
        top_k: int | None,
        repository: str | None,
    ) -> list[RetrievedChunk]:
        captured["repository"] = repository
        return [source]

    monkeypatch.setattr(rag, "search_code", fake_search)
    monkeypatch.setattr(rag, "_create_client", lambda *args: client)

    result = rag.answer_question(
        fake_db,
        "How does addition work?",
        top_k=1,
        repository="tiny-repo",
    )

    assert result.answer == "Addition returns left + right."
    assert result.sources == [source]
    assert captured["rolled_back"] is True
    assert captured["client_closed"] is True
    assert captured["model"] == "test-model"
    assert captured["repository"] == "tiny-repo"
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert "Do not invent repository behavior" in messages[0]["content"]
    assert "calculator.py" in messages[1]["content"]


def test_answer_question_sources_only_include_context_sent_to_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rag, "MAX_CONTEXT_CHARACTERS", 300)
    excluded = RetrievedChunk(
        repository="tiny-repo",
        file_path="excluded.py",
        symbol_type="module",
        symbol_name=None,
        start_line=1,
        end_line=100,
        content="x" * 500,
        cosine_distance=0.1,
    )
    included = RetrievedChunk(
        repository="tiny-repo",
        file_path="included.py",
        symbol_type="function",
        symbol_name="small",
        start_line=1,
        end_line=2,
        content="return 1",
        cosine_distance=0.2,
    )
    settings = SimpleNamespace(
        llm_api_key="test-key",
        llm_model_name="test-model",
        llm_base_url=None,
        llm_timeout_seconds=30.0,
        llm_max_retries=0,
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="grounded"))]
                )
            )
        ),
        close=lambda: None,
    )
    db = SimpleNamespace(rollback=lambda: None)
    monkeypatch.setattr(rag, "get_settings", lambda: settings)
    monkeypatch.setattr(rag, "search_code", lambda *args: [excluded, included])
    monkeypatch.setattr(rag, "_create_client", lambda *args: client)

    result = rag.answer_question(db, "What does this do?")

    assert result.sources == [included]


def test_answer_question_reports_upstream_failure_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SyntheticProviderError(Exception):
        pass

    settings = SimpleNamespace(
        llm_api_key="test-key",
        llm_model_name="test-model",
        llm_base_url=None,
        llm_timeout_seconds=30.0,
        llm_max_retries=0,
    )
    closed = False

    def fail_create(**kwargs: object) -> None:
        raise SyntheticProviderError("synthetic provider secret")

    def close() -> None:
        nonlocal closed
        closed = True

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fail_create)),
        close=close,
    )
    monkeypatch.setattr(rag, "OpenAIError", SyntheticProviderError)
    monkeypatch.setattr(rag, "get_settings", lambda: settings)
    monkeypatch.setattr(rag, "search_code", lambda *args: [])
    monkeypatch.setattr(rag, "_create_client", lambda *args: client)

    with pytest.raises(rag.RAGGenerationError, match="LLM request failed"):
        rag.answer_question(SimpleNamespace(rollback=lambda: None), "question")

    assert closed is True


def test_answer_question_rejects_malformed_llm_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        llm_api_key="test-key",
        llm_model_name="test-model",
        llm_base_url=None,
        llm_timeout_seconds=30.0,
        llm_max_retries=0,
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(choices=[]))
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(rag, "get_settings", lambda: settings)
    monkeypatch.setattr(rag, "search_code", lambda *args: [])
    monkeypatch.setattr(rag, "_create_client", lambda *args: client)

    with pytest.raises(rag.RAGGenerationError, match="did not contain an answer"):
        rag.answer_question(SimpleNamespace(rollback=lambda: None), "question")
