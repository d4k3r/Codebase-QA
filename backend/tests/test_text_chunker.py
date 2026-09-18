"""Tests for bounded config-text chunks and source provenance."""

from pathlib import Path

import pytest

from app.services import text_chunker


def test_config_chunk_preserves_exact_source_and_line_provenance(
    tmp_path: Path,
) -> None:
    source = "services:\n  postgres:\n    image: pgvector/example\n"
    path = tmp_path / "compose.yml"
    path.write_text(source, encoding="utf-8")

    chunks = text_chunker.chunk_config_file(path, tmp_path, "config-repo")

    assert len(chunks) == 1
    assert chunks[0].symbol_type == "config"
    assert chunks[0].symbol_name is None
    assert (chunks[0].start_line, chunks[0].end_line) == (1, 3)
    assert chunks[0].content == source


def test_config_chunks_are_bounded_contiguous_and_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(text_chunker, "MAX_CONFIG_CHUNK_CHARACTERS", 12)
    source = "first: 123\nsecond: 456\nthird: 789\n"
    path = tmp_path / "bounded.yaml"
    path.write_text(source, encoding="utf-8")

    first = text_chunker.chunk_config_file(path, tmp_path, "config-repo")
    second = text_chunker.chunk_config_file(path, tmp_path, "config-repo")

    assert first == second
    assert all(len(chunk.content) <= 12 for chunk in first)
    assert "".join(chunk.content for chunk in first) == source
    source_lines = source.splitlines(keepends=True)
    for chunk in first:
        selected_lines = "".join(
            source_lines[chunk.start_line - 1 : chunk.end_line]
        )
        assert chunk.content in selected_lines


def test_oversized_single_line_is_split_without_fabricating_line_numbers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(text_chunker, "MAX_CONFIG_CHUNK_CHARACTERS", 8)
    source = "abcdefghijklmnopqrst"
    path = tmp_path / "long.sql"
    path.write_text(source, encoding="utf-8")

    chunks = text_chunker.chunk_config_file(path, tmp_path, "config-repo")

    assert [chunk.content for chunk in chunks] == ["abcdefgh", "ijklmnop", "qrst"]
    assert [(chunk.start_line, chunk.end_line) for chunk in chunks] == [
        (1, 1),
        (1, 1),
        (1, 1),
    ]


def test_whitespace_only_config_file_emits_no_chunks(tmp_path: Path) -> None:
    path = tmp_path / "empty.yml"
    path.write_text(" \n\n\t", encoding="utf-8")

    assert text_chunker.chunk_config_file(path, tmp_path, "config-repo") == []
