"""Discover Python source files in a local repository."""

import os
from pathlib import Path


EXCLUDED_DIRECTORIES = frozenset(
    {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist"}
)


class RepositoryPathError(ValueError):
    """Raised when a local repository path cannot be indexed."""


class RepositoryReadError(RepositoryPathError):
    """Raised when repository traversal cannot safely complete."""


def resolve_repository_root(repository_path: str | Path) -> Path:
    """Resolve and validate a local repository directory."""

    root = Path(repository_path).expanduser().resolve()
    if not root.exists():
        raise RepositoryPathError(f"Repository path does not exist: {root}")
    if not root.is_dir():
        raise RepositoryPathError(f"Repository path is not a directory: {root}")
    return root


def discover_python_files(repository_path: str | Path) -> list[Path]:
    """Return repository Python files in deterministic relative-path order."""

    root = resolve_repository_root(repository_path)
    discovered: list[Path] = []

    def read_entries(directory: Path) -> list[os.DirEntry[str]]:
        try:
            with os.scandir(directory) as entries:
                return sorted(entries, key=lambda entry: entry.name)
        except OSError as exc:
            raise RepositoryReadError(
                f"Could not read repository directory {directory}: {exc}"
            ) from exc

    def visit(directory: Path) -> None:
        for entry in read_entries(directory):
            try:
                is_directory = entry.is_dir(follow_symlinks=False)
                if is_directory:
                    if entry.name not in EXCLUDED_DIRECTORIES:
                        visit(Path(entry.path))
                elif entry.name.endswith(".py") and entry.is_file(follow_symlinks=False):
                    discovered.append(Path(entry.path))
            except OSError as exc:
                raise RepositoryReadError(
                    f"Could not classify repository entry {entry.path}: {exc}"
                ) from exc

    visit(root)

    return sorted(discovered, key=lambda path: path.relative_to(root).as_posix())
