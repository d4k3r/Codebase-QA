"""Retrieve bounded repository context and request one grounded LLM answer."""

from dataclasses import dataclass

from openai import OpenAI, OpenAIError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.services.retrieval import RetrievedChunk, search_code


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


def build_context(chunks: list[RetrievedChunk]) -> str:
    """Build a readable context block with a simple character bound."""

    sections: list[str] = []
    used = 0

    for chunk in chunks:
        symbol = chunk.symbol_name or "<module>"
        header = (
            f"--- {chunk.repository}/{chunk.file_path} "
            f"[{chunk.symbol_type} {symbol}, lines {chunk.start_line}-{chunk.end_line}] ---\n"
        )
        separator = "\n\n" if sections else ""
        available = MAX_CONTEXT_CHARACTERS - used - len(separator) - len(header)
        if available <= 0:
            break
        content = chunk.content[:available]
        sections.append(header + content)
        used += len(separator) + len(header) + len(content)
        if used == MAX_CONTEXT_CHARACTERS:
            break

    return "\n\n".join(sections) if sections else "No repository context was retrieved."


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
    options: dict[str, str] = {"api_key": api_key}
    if settings.llm_base_url and settings.llm_base_url.strip():
        options["base_url"] = settings.llm_base_url.strip()
    return OpenAI(**options)


def answer_question(
    db: Session,
    question: str,
    top_k: int | None = None,
) -> RAGResult:
    """Run retrieval and ask one OpenAI-compatible chat-completions endpoint."""

    if not question.strip():
        raise ValueError("Question must not be empty")

    settings = get_settings()
    api_key, model = _required_llm_config(settings)
    sources = search_code(db, question, top_k)
    context = build_context(sources)
    user_prompt = f"Question:\n{question}\n\nRepository context:\n{context}"

    try:
        completion = _create_client(settings, api_key).chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except OpenAIError as exc:
        raise RAGGenerationError(f"LLM request failed: {exc}") from exc

    try:
        answer = completion.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise RAGGenerationError("LLM response did not contain an answer") from exc
    if not answer:
        raise RAGGenerationError("LLM returned an empty answer")
    return RAGResult(answer=answer, sources=sources)
