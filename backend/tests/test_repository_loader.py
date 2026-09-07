"""Tests for local Python repository discovery."""

from pathlib import Path

import pytest

from app.services.repository_loader import RepositoryPathError, discover_python_files


def test_discovers_python_files_in_deterministic_order(tiny_repository: Path) -> None:
    files = discover_python_files(tiny_repository)

    assert [path.relative_to(tiny_repository).as_posix() for path in files] == [
        "calculator.py",
        "constants.py",
        "nested/greetings.py",
    ]


def test_rejects_missing_repository(tmp_path: Path) -> None:
    with pytest.raises(RepositoryPathError, match="does not exist"):
        discover_python_files(tmp_path / "missing")


def test_rejects_file_instead_of_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-repository.py"
    file_path.write_text("pass\n", encoding="utf-8")

    with pytest.raises(RepositoryPathError, match="not a directory"):
        discover_python_files(file_path)
