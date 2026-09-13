"""Tests for local Python repository discovery."""

import os
from pathlib import Path

import pytest

from app.services import repository_loader
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


def test_surfaces_filesystem_traversal_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_scandir(directory: Path):
        raise PermissionError(f"synthetic permission denied: {directory}")

    monkeypatch.setattr(repository_loader.os, "scandir", failing_scandir)

    with pytest.raises(RepositoryPathError, match="Could not read repository directory"):
        discover_python_files(tmp_path)


def test_surfaces_directory_entry_classification_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingEntry:
        name = "unreadable.py"
        path = str(tmp_path / name)

        def is_dir(self, *, follow_symlinks: bool) -> bool:
            del follow_symlinks
            raise OSError("synthetic classification failure")

    class ScanResult:
        def __enter__(self) -> "ScanResult":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def __iter__(self):
            return iter([FailingEntry()])

    monkeypatch.setattr(repository_loader.os, "scandir", lambda directory: ScanResult())

    with pytest.raises(RepositoryPathError, match="Could not classify repository entry"):
        discover_python_files(tmp_path)


def test_ignores_nonregular_python_files(tmp_path: Path) -> None:
    fifo_path = tmp_path / "named_pipe.py"
    try:
        os.mkfifo(fifo_path)
    except (AttributeError, NotImplementedError):
        pytest.skip("FIFO creation is unavailable on this platform")

    assert discover_python_files(tmp_path) == []
