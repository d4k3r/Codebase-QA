"""Retrieve bounded repository context and request one grounded LLM answer."""

from dataclasses import dataclass

from openai import OpenAI, OpenAIError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.services.retrieval import RetrievalError, RetrievedChunk, search_code


MAX_CONTEXT_CHARACTERS = 12_000
SYSTEM_PROMPT = """You answer questions about a repository from supplied context only.
Do not invent repository behavior that is not supported by the context.
If the supplied context is insufficient, say so clearly.
When useful, refer to source file paths and line ranges from the context."""


class LLMConfigurationError(RuntimeError):
    """Raised when required LLM configuration is absent."""


class RAGGenerationError(RuntimeError):
    """Raised when the configured LLM cannot generate an answer."""


@dataclass(frozen=True, slots=True)
class RAGResult:
    answer: str
    sources: list[RetrievedChunk]


@dataclass(frozen=True, slots=True)
class ContextBuild:
    """The exact complete chunks included in the model context."""

    text: str
    included_chunks: list[RetrievedChunk]


def build_context(chunks: list[RetrievedChunk]) -> ContextBuild:
    """Build bounded context without partially supplying any source chunk."""

    sections: list[str] = []
    included_chunks: list[RetrievedChunk] = []
    used = 0

    for chunk in chunks:
        symbol = chunk.symbol_name or "<module>"
        header = (
            f"--- {chunk.repository}/{chunk.file_path} "
            f"[{chunk.symbol_type} {symbol}, lines {chunk.start_line}-{chunk.end_line}] ---\n"
        )
        separator = "\n\n" if sections else ""
        section = header + chunk.content
        required = len(separator) + len(section)
        if used + required > MAX_CONTEXT_CHARACTERS:
            continue
        sections.append(section)
        included_chunks.append(chunk)
        used += required

    return ContextBuild(
        text="\n\n".join(sections) if sections else "No repository context was retrieved.",
        included_chunks=included_chunks,
    )


def _required_llm_config(settings: Settings) -> tuple[str, str]:
    api_key = (settings.llm_api_key or "").strip()
    model = (settings.llm_model_name or "").strip()
    missing = [
        name
        for name, value in (("LLM_API_KEY", api_key), ("LLM_MODEL_NAME", model))
        if not value
    ]
    if missing:
        raise LLMConfigurationError(
            f"Missing required LLM configuration: {', '.join(missing)}"
        )
    return api_key, model


def _create_client(settings: Settings, api_key: str) -> OpenAI:
    options: dict[str, object] = {
        "api_key": api_key,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }
    if settings.llm_base_url and settings.llm_base_url.strip():
        options["base_url"] = settings.llm_base_url.strip()
    return OpenAI(**options)


def answer_question(
    db: Session,
    question: str,
    top_k: int | None = None,
    repository: str | None = None,
) -> RAGResult:
    """Run retrieval and ask one OpenAI-compatible chat-completions endpoint."""

    if not question.strip():
        raise ValueError("Question must not be empty")

    settings = get_settings()
    api_key, model = _required_llm_config(settings)
    try:
        retrieval_candidates = search_code(db, question, top_k, repository)
        # search_code performs a read-only SELECT. End its transaction before
        # waiting on the external LLM while retaining ownership of the Session.
        db.rollback()
    except RetrievalError:
        raise
    except SQLAlchemyError as exc:
        raise RetrievalError("Could not finalize retrieval transaction") from exc

    context = build_context(retrieval_candidates)
    user_prompt = f"Question:\n{question}\n\nRepository context:\n{context.text}"

    client = _create_client(settings, api_key)
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except OpenAIError as exc:
        raise RAGGenerationError(f"LLM request failed: {exc}") from exc
    finally:
        client.close()

    try:
        answer = completion.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise RAGGenerationError("LLM response did not contain an answer") from exc
    if not answer:
        raise RAGGenerationError("LLM returned an empty answer")
    return RAGResult(answer=answer, sources=context.included_chunks)
