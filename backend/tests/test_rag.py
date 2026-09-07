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

    assert "tiny-repo/calculator.py" in context
    assert "lines 4-6" in context
    assert "return left + right" in context
    assert len(context) <= rag.MAX_CONTEXT_CHARACTERS


def test_build_context_enforces_bound_across_multiple_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rag, "MAX_CONTEXT_CHARACTERS", 300)
    source = RetrievedChunk(
        repository="tiny-repo",
        file_path="large.py",
        symbol_type="module",
        symbol_name=None,
        start_line=1,
        end_line=100,
        content="x" * 500,
        cosine_distance=0.2,
    )

    assert len(rag.build_context([source, source])) <= 300


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
    )
    monkeypatch.setattr(rag, "get_settings", lambda: settings)
    monkeypatch.setattr(rag, "search_code", lambda *args: [source])
    monkeypatch.setattr(rag, "_create_client", lambda *args: client)

    result = rag.answer_question(object(), "How does addition work?", top_k=1)  # type: ignore[arg-type]

    assert result.answer == "Addition returns left + right."
    assert result.sources == [source]
    assert captured["model"] == "test-model"
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert "Do not invent repository behavior" in messages[0]["content"]
    assert "calculator.py" in messages[1]["content"]
