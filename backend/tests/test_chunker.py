"""Tests for AST-aware source chunking and metadata."""

from pathlib import Path

import pytest

from app.services.chunker import SourceFileError, chunk_python_file


def test_chunks_top_level_function_and_class_with_exact_source(
    tiny_repository: Path,
) -> None:
    chunks = chunk_python_file(
        tiny_repository / "calculator.py", tiny_repository, "tiny-repo"
    )

    assert [(chunk.symbol_type, chunk.symbol_name) for chunk in chunks] == [
        ("function", "add"),
        ("class", "Calculator"),
    ]
    assert chunks[0].file_path == "calculator.py"
    assert (chunks[0].start_line, chunks[0].end_line) == (4, 6)
    assert chunks[0].content == (
        "def add(left: int, right: int) -> int:\n"
        '    """Return the sum of two integers."""\n'
        "    return left + right\n"
    )
    assert (chunks[1].start_line, chunks[1].end_line) == (9, 14)
    assert "def multiply" in chunks[1].content
    assert all(chunk.symbol_name != "multiply" for chunk in chunks)


def test_chunks_async_function(tiny_repository: Path) -> None:
    chunks = chunk_python_file(
        tiny_repository / "nested" / "greetings.py", tiny_repository, "tiny-repo"
    )

    assert len(chunks) == 1
    assert chunks[0].symbol_type == "async_function"
    assert chunks[0].symbol_name == "greet"
    assert chunks[0].file_path == "nested/greetings.py"
    assert (chunks[0].start_line, chunks[0].end_line) == (1, 3)


def test_creates_module_fallback_chunk(tiny_repository: Path) -> None:
    path = tiny_repository / "constants.py"
    chunks = chunk_python_file(path, tiny_repository, "tiny-repo")

    assert len(chunks) == 1
    assert chunks[0].symbol_type == "module"
    assert chunks[0].symbol_name is None
    assert (chunks[0].start_line, chunks[0].end_line) == (1, 3)
    assert chunks[0].content == path.read_text(encoding="utf-8")


def test_reports_invalid_python_source(tmp_path: Path) -> None:
    invalid_file = tmp_path / "invalid.py"
    invalid_file.write_text("def broken(:\n", encoding="utf-8")

    with pytest.raises(SourceFileError, match="Invalid Python syntax"):
        chunk_python_file(invalid_file, tmp_path, "invalid-repo")
