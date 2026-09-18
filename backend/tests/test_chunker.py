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
        ("module_companion", None),
        ("function", "add"),
        ("class", "Calculator"),
    ]
    assert chunks[1].file_path == "calculator.py"
    assert (chunks[0].start_line, chunks[0].end_line) == (1, 1)
    assert chunks[0].content == '"""Small arithmetic helpers used by tests."""\n'
    assert (chunks[1].start_line, chunks[1].end_line) == (4, 6)
    assert chunks[1].content == (
        "def add(left: int, right: int) -> int:\n"
        '    """Return the sum of two integers."""\n'
        "    return left + right\n"
    )
    assert (chunks[2].start_line, chunks[2].end_line) == (9, 14)
    assert "def multiply" in chunks[2].content
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


def test_decorated_symbols_include_multiline_decorators(tmp_path: Path) -> None:
    source = (
        "@route(\n"
        "    '/items',\n"
        ")\n"
        "def get_items():\n"
        "    return []\n"
        "\n"
        "@dataclass(\n"
        "    frozen=True,\n"
        ")\n"
        "class Item:\n"
        "    value: int\n"
        "\n"
        "    def method(self):\n"
        "        return self.value\n"
    )
    path = tmp_path / "decorated.py"
    path.write_text(source, encoding="utf-8")

    chunks = chunk_python_file(path, tmp_path, "decorated-repo")

    assert [(chunk.symbol_type, chunk.symbol_name) for chunk in chunks] == [
        ("function", "get_items"),
        ("class", "Item"),
    ]
    assert (chunks[0].start_line, chunks[0].end_line) == (1, 5)
    assert chunks[0].content == "".join(source.splitlines(keepends=True)[:5])
    assert (chunks[1].start_line, chunks[1].end_line) == (7, 14)
    assert chunks[1].content.startswith("@dataclass(\n    frozen=True,\n)\nclass Item:")
    assert "def method" in chunks[1].content


def test_parenthesised_decorator_chunk_starts_at_opening_line(tmp_path: Path) -> None:
    source = "@(\n    decorator\n)\ndef decorated():\n    return 1\n"
    path = tmp_path / "parenthesised.py"
    path.write_text(source, encoding="utf-8")

    [chunk] = chunk_python_file(path, tmp_path, "decorated-repo")

    assert (chunk.start_line, chunk.end_line) == (1, 5)
    assert chunk.content == source


def test_companion_spans_cover_meaningful_uncovered_module_regions(
    tmp_path: Path,
) -> None:
    source = (
        "import os\n"
        "VALUE = 1\n"
        "\n"
        "@decorator\n"
        "def function():\n"
        "    return VALUE\n"
        "\n"
        "client = object()\n"
        "\n"
        "class Thing:\n"
        "    pass\n"
        "\n"
        "if os.getenv('RUN'):\n"
        "    function()\n"
    )
    path = tmp_path / "mixed.py"
    path.write_text(source, encoding="utf-8")

    chunks = chunk_python_file(path, tmp_path, "mixed-repo")

    assert [
        (chunk.symbol_type, chunk.symbol_name, chunk.start_line, chunk.end_line)
        for chunk in chunks
    ] == [
        ("module_companion", None, 1, 2),
        ("function", "function", 4, 6),
        ("module_companion", None, 8, 8),
        ("class", "Thing", 10, 11),
        ("module_companion", None, 13, 14),
    ]
    source_lines = source.splitlines(keepends=True)
    for chunk in chunks:
        assert chunk.content == "".join(
            source_lines[chunk.start_line - 1 : chunk.end_line]
        )
    assert chunks[1].content.startswith("@decorator\n")
    assert chunks[-1].content == "if os.getenv('RUN'):\n    function()\n"


def test_comment_and_whitespace_only_regions_do_not_create_companions(
    tmp_path: Path,
) -> None:
    source = "# module comment\n\n\ndef only_symbol():\n    return 1\n\n# trailing\n"
    path = tmp_path / "comments.py"
    path.write_text(source, encoding="utf-8")

    chunks = chunk_python_file(path, tmp_path, "comments-repo")

    assert [(chunk.symbol_type, chunk.symbol_name) for chunk in chunks] == [
        ("function", "only_symbol")
    ]
    assert chunks[0].content == "def only_symbol():\n    return 1\n"


def test_chunking_is_deterministic_for_repeated_reads(tmp_path: Path) -> None:
    source = "SETTING = 1\n\ndef use_setting():\n    return SETTING\n"
    path = tmp_path / "stable.py"
    path.write_text(source, encoding="utf-8")

    first = chunk_python_file(path, tmp_path, "stable-repo")
    second = chunk_python_file(path, tmp_path, "stable-repo")

    assert first == second
