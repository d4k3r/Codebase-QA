"""Tests for local Python repository discovery."""

import os
from pathlib import Path

import pytest

from app.services import repository_loader
from app.services.repository_loader import (
    RepositoryPathError,
    discover_python_files,
    discover_source_files,
)


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


def test_discovers_only_deliberately_supported_config_files(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "settings.yaml").write_text("enabled: true\n", encoding="utf-8")
    (tmp_path / "init.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (tmp_path / "vite.config.ts").write_text("export default {};\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("SETTING=example\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=do-not-index\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("not allowlisted\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    files = discover_source_files(tmp_path)

    assert [path.name for path in files] == [
        ".env.example",
        "docker-compose.yml",
        "init.sql",
        "module.py",
        "settings.yaml",
        "vite.config.ts",
    ]


def test_config_discovery_excludes_binary_and_generated_or_vendor_files(
    tmp_path: Path,
) -> None:
    (tmp_path / "binary.sql").write_bytes(b"SELECT\x00binary")
    for directory_name in ("build", "dist", "node_modules", "vendor"):
        directory = tmp_path / directory_name
        directory.mkdir()
        (directory / "hidden.py").write_text("VALUE = 1\n", encoding="utf-8")
        (directory / "hidden.yml").write_text("value: 1\n", encoding="utf-8")

    assert discover_source_files(tmp_path) == []
