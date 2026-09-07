"""Discover Python source files in a local repository."""

from pathlib import Path


EXCLUDED_DIRECTORIES = frozenset(
    {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist"}
)


class RepositoryPathError(ValueError):
    """Raised when a local repository path cannot be indexed."""


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

    try:
        for path in root.rglob("*.py"):
            relative_path = path.relative_to(root)
            if any(part in EXCLUDED_DIRECTORIES for part in relative_path.parts[:-1]):
                continue
            if path.is_file():
                discovered.append(path)
    except OSError as exc:
        raise RepositoryPathError(f"Could not read repository directory {root}: {exc}") from exc

    return sorted(discovered, key=lambda path: path.relative_to(root).as_posix())
