"""Create bounded, contiguous chunks for deliberately supported config files."""

from pathlib import Path

from app.services.chunker import SourceChunk, SourceFileError, SourceReadError


MAX_CONFIG_CHUNK_CHARACTERS = 4_000


def _bounded_line_pieces(source: str) -> list[tuple[int, str]]:
    """Split source into bounded pieces while retaining original characters."""

    pieces: list[tuple[int, str]] = []
    for line_number, line in enumerate(source.splitlines(keepends=True), start=1):
        if not line:
            continue
        for offset in range(0, len(line), MAX_CONFIG_CHUNK_CHARACTERS):
            pieces.append(
                (line_number, line[offset : offset + MAX_CONFIG_CHUNK_CHARACTERS])
            )
    return pieces


def chunk_config_file(
    file_path: str | Path,
    repository_root: str | Path,
    repository_name: str,
) -> list[SourceChunk]:
    """Chunk one supported UTF-8 config file without applying Python semantics."""

    root = Path(repository_root).resolve()
    path = Path(file_path).resolve()
    try:
        relative_path = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise SourceFileError(f"Source file is outside repository root: {path}") from exc

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SourceReadError(
            f"Could not read config source file {relative_path}: {exc}"
        ) from exc

    if not source.strip():
        return []

    chunks: list[SourceChunk] = []
    pending: list[tuple[int, str]] = []
    pending_size = 0

    def flush() -> None:
        nonlocal pending_size
        if pending and "".join(text for _, text in pending).strip():
            chunks.append(
                SourceChunk(
                    repository=repository_name,
                    file_path=relative_path,
                    symbol_type="config",
                    symbol_name=None,
                    start_line=pending[0][0],
                    end_line=pending[-1][0],
                    content="".join(text for _, text in pending),
                )
            )
        pending.clear()
        pending_size = 0

    for line_number, text in _bounded_line_pieces(source):
        if pending and pending_size + len(text) > MAX_CONFIG_CHUNK_CHARACTERS:
            flush()
        pending.append((line_number, text))
        pending_size += len(text)
    flush()
    return chunks
