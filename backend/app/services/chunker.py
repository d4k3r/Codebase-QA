"""Create exact source chunks for top-level Python symbols using the AST."""

import ast
from dataclasses import dataclass
from pathlib import Path


class SourceFileError(ValueError):
    """Raised when a Python source file cannot be read or parsed."""


@dataclass(frozen=True, slots=True)
class SourceChunk:
    """A parsed code chunk before it is converted to an ORM model."""

    repository: str
    file_path: str
    symbol_type: str
    symbol_name: str | None
    start_line: int
    end_line: int
    content: str


def _symbol_type(node: ast.AST) -> str:
    if isinstance(node, ast.AsyncFunctionDef):
        return "async_function"
    if isinstance(node, ast.FunctionDef):
        return "function"
    return "class"


def chunk_python_file(
    file_path: str | Path,
    repository_root: str | Path,
    repository_name: str,
) -> list[SourceChunk]:
    """Extract top-level functions/classes or one module fallback chunk."""

    root = Path(repository_root).resolve()
    path = Path(file_path).resolve()
    try:
        relative_path = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise SourceFileError(f"Source file is outside repository root: {path}") from exc

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SourceFileError(f"Could not read Python source file {relative_path}: {exc}") from exc

    try:
        tree = ast.parse(source, filename=relative_path)
    except SyntaxError as exc:
        location = f"line {exc.lineno}" if exc.lineno is not None else "unknown line"
        raise SourceFileError(
            f"Invalid Python syntax in {relative_path} at {location}: {exc.msg}"
        ) from exc

    source_lines = source.splitlines(keepends=True)
    chunks: list[SourceChunk] = []
    supported_nodes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    for node in tree.body:
        if not isinstance(node, supported_nodes):
            continue
        if node.end_lineno is None:
            raise SourceFileError(f"Missing end-line metadata for {relative_path}")

        chunks.append(
            SourceChunk(
                repository=repository_name,
                file_path=relative_path,
                symbol_type=_symbol_type(node),
                symbol_name=node.name,
                start_line=node.lineno,
                end_line=node.end_lineno,
                content="".join(source_lines[node.lineno - 1 : node.end_lineno]),
            )
        )

    if not chunks and tree.body and source.strip():
        chunks.append(
            SourceChunk(
                repository=repository_name,
                file_path=relative_path,
                symbol_type="module",
                symbol_name=None,
                start_line=1,
                end_line=max(1, len(source.splitlines())),
                content=source,
            )
        )

    return chunks
