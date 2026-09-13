"""Create exact source chunks for top-level Python symbols using the AST."""

import ast
import io
import tokenize
from dataclasses import dataclass
from pathlib import Path


class SourceFileError(ValueError):
    """Raised when a Python source file cannot be read or parsed."""


class SourceReadError(SourceFileError):
    """Raised when a Python source file cannot be read safely."""


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


def _decorator_start_line(source: str, decorator: ast.expr) -> int:
    """Find the decorator's ``@`` line, including parenthesised expressions."""

    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    target_line = decorator.lineno
    target_column = decorator.col_offset
    target_index = next(
        (
            index
            for index, token in enumerate(tokens)
            if token.start[0] == target_line
            and token.start[1] >= target_column
            and token.type not in {tokenize.INDENT, tokenize.DEDENT, tokenize.NL}
        ),
        None,
    )
    if target_index is None:
        return target_line

    for token in reversed(tokens[: target_index + 1]):
        if token.type == tokenize.OP and token.string == "@":
            return token.start[0]
    return target_line


def _start_line(
    source: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> int:
    """Return the first source line belonging to a symbol, including decorators."""

    decorator_lines = [
        _decorator_start_line(source, decorator) for decorator in node.decorator_list
    ]
    return min([node.lineno, *decorator_lines])


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
        raise SourceReadError(
            f"Could not read Python source file {relative_path}: {exc}"
        ) from exc

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
                start_line=_start_line(source, node),
                end_line=node.end_lineno,
                content="".join(
                    source_lines[_start_line(source, node) - 1 : node.end_lineno]
                ),
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
