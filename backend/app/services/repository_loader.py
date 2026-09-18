"""Discover deliberately supported source files in a local repository."""

import os
from pathlib import Path


EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "build",
        "dist",
        "vendor",
    }
)
SUPPORTED_CONFIG_SUFFIXES = frozenset({".sql", ".yaml", ".yml"})
SUPPORTED_CONFIG_FILENAMES = frozenset({".env.example", "vite.config.ts"})


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


def _is_supported_config_path(path: Path) -> bool:
    return (
        path.name in SUPPORTED_CONFIG_FILENAMES
        or path.suffix.lower() in SUPPORTED_CONFIG_SUFFIXES
    )


def _is_utf8_text_file(path: Path) -> bool:
    """Reject binary/non-UTF-8 config candidates before source loading."""

    try:
        with path.open("rb") as source_file:
            sample = source_file.read(4096)
    except OSError as exc:
        raise RepositoryReadError(f"Could not read repository file {path}: {exc}") from exc
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def discover_python_files(
    repository_path: str | Path,
    *,
    include_config: bool = False,
) -> list[Path]:
    """Return supported regular files in deterministic relative-path order."""

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
                elif entry.is_file(follow_symlinks=False):
                    path = Path(entry.path)
                    if entry.name.endswith(".py"):
                        discovered.append(path)
                    elif (
                        include_config
                        and _is_supported_config_path(path)
                        and _is_utf8_text_file(path)
                    ):
                        discovered.append(path)
            except OSError as exc:
                raise RepositoryReadError(
                    f"Could not classify repository entry {entry.path}: {exc}"
                ) from exc

    visit(root)

    return sorted(discovered, key=lambda path: path.relative_to(root).as_posix())


def discover_source_files(repository_path: str | Path) -> list[Path]:
    """Return Python plus the deliberate config-text allowlist."""

    return discover_python_files(repository_path, include_config=True)
