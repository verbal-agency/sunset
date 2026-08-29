"""Strict AST collection for Python compatibility guards and import fallbacks."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
from pathlib import Path

from sunset.compatibility_models import (
    COMPATIBILITY_SCHEMA_VERSION,
    CompatibilityCandidate,
    CompatibilityScanResult,
    SourceSpan,
)
from sunset.git_repository import GitRepository, RepositoryError
from sunset.models import ScanError


_COMPARATORS = {
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Eq: "==",
    ast.NotEq: "!=",
}


@dataclass(frozen=True, slots=True)
class _DiscoveredCompatibility:
    candidate_kind: str
    line: int
    column: int
    condition: str | None
    comparator: str | None
    subject: str | None
    threshold: str | None
    guard_span: SourceSpan
    protected_span: SourceSpan
    fallback_span: SourceSpan | None
    protected_imports: tuple[str, ...]
    fallback_imports: tuple[str, ...]


class _CompatibilityVisitor(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.source = source
        self.candidates: list[_DiscoveredCompatibility] = []

    def visit_If(self, node: ast.If) -> None:
        discovery = _parse_guard(node, self.source)
        if discovery is not None:
            self.candidates.append(discovery)
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        discovery = _parse_import_fallback(node)
        if discovery is not None:
            self.candidates.append(discovery)
        self.generic_visit(node)


def scan_compatibility_repository(target: str | Path) -> CompatibilityScanResult:
    """Scan committed Python sources without importing or evaluating them."""

    repository = GitRepository.open(target)
    candidates: list[CompatibilityCandidate] = []
    errors: list[ScanError] = []
    for path in repository.list_python_files():
        try:
            source = repository.read_text(path)
        except RepositoryError as exc:
            errors.append(ScanError(kind=exc.code, path=path, message=exc.message))
            continue
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            errors.append(
                ScanError(
                    kind="parse_error", path=path, message=exc.msg,
                    line=exc.lineno, column=exc.offset,
                )
            )
            continue
        visitor = _CompatibilityVisitor(source)
        visitor.visit(tree)
        for discovery in visitor.candidates:
            try:
                blame_commit = repository.blame_commit(path, discovery.line)
            except RepositoryError as exc:
                errors.append(
                    ScanError(
                        kind=exc.code, path=path, message=exc.message,
                        line=discovery.line, column=discovery.column,
                    )
                )
                continue
            candidates.append(
                CompatibilityCandidate(
                    candidate_id=_candidate_id(repository.head, path, discovery),
                    candidate_kind=discovery.candidate_kind,
                    path=path,
                    line=discovery.line,
                    column=discovery.column,
                    condition=discovery.condition,
                    comparator=discovery.comparator,
                    subject=discovery.subject,
                    threshold=discovery.threshold,
                    guard_span=discovery.guard_span,
                    protected_span=discovery.protected_span,
                    fallback_span=discovery.fallback_span,
                    protected_imports=discovery.protected_imports,
                    fallback_imports=discovery.fallback_imports,
                    repository_head=repository.head,
                    blame_commit=blame_commit,
                )
            )
    candidates.sort(key=lambda item: (item.path, item.line, item.column, item.candidate_kind))
    errors.sort(key=lambda item: (item.path, item.line or -1, item.column or -1, item.kind))
    return CompatibilityScanResult(
        repository_head=repository.head,
        candidates=tuple(candidates),
        errors=tuple(errors),
    )


def _parse_guard(node: ast.If, source: str) -> _DiscoveredCompatibility | None:
    paths = _branch_imports(node.body), _branch_imports(node.orelse)
    if paths[0] is None or paths[1] is None:
        return None
    expression = _guard_expression(node.test)
    if expression is None:
        return None
    candidate_kind, comparator, subject, threshold = expression
    return _DiscoveredCompatibility(
        candidate_kind=candidate_kind,
        line=node.lineno,
        column=node.col_offset,
        condition=_source(source, node.test),
        comparator=comparator,
        subject=subject,
        threshold=threshold,
        guard_span=_span(node),
        protected_span=_span_for_statements(node.body),
        fallback_span=_span_for_statements(node.orelse),
        protected_imports=paths[0],
        fallback_imports=paths[1],
    )


def _parse_import_fallback(node: ast.Try) -> _DiscoveredCompatibility | None:
    if node.orelse or node.finalbody or len(node.handlers) != 1:
        return None
    handler = node.handlers[0]
    if not isinstance(handler.type, ast.Name) or handler.type.id not in {"ImportError", "ModuleNotFoundError"}:
        return None
    protected = _branch_imports(node.body)
    fallback = _branch_imports(handler.body)
    if protected is None or fallback is None:
        return None
    return _DiscoveredCompatibility(
        candidate_kind="import_fallback",
        line=node.lineno,
        column=node.col_offset,
        condition=handler.type.id,
        comparator=None,
        subject=None,
        threshold=None,
        guard_span=_span(node),
        protected_span=_span_for_statements(node.body),
        fallback_span=_span_for_statements(handler.body),
        protected_imports=protected,
        fallback_imports=fallback,
    )


def _guard_expression(test: ast.expr) -> tuple[str, str, str, str] | None:
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return None
    comparator = _COMPARATORS.get(type(test.ops[0]))
    if comparator is None:
        return None
    if _is_sys_version_info(test.left):
        threshold = _literal_version_tuple(test.comparators[0])
        if threshold is not None:
            return "runtime_version_guard", comparator, "runtime:python", threshold
    dependency = _dependency_subject(test.left)
    threshold = _dependency_threshold(test.comparators[0])
    if dependency is not None and threshold is not None:
        return "dependency_version_guard", comparator, f"dependency:{dependency}", threshold
    return None


def _is_sys_version_info(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and _attribute_chain(node) == ("sys", "version_info")


def _literal_version_tuple(node: ast.expr) -> str | None:
    if not isinstance(node, ast.Tuple) or not node.elts or len(node.elts) > 3:
        return None
    values: list[str] = []
    for value in node.elts:
        if not isinstance(value, ast.Constant) or not isinstance(value.value, int):
            return None
        values.append(str(value.value))
    return ".".join(values)


def _dependency_subject(node: ast.expr) -> str | None:
    if _metadata_version_call(node) is not None:
        return _metadata_version_call(node)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Version" and len(node.args) == 1 and not node.keywords:
        return _metadata_version_call(node.args[0])
    return None


def _metadata_version_call(node: ast.expr) -> str | None:
    if not isinstance(node, ast.Call) or len(node.args) != 1 or node.keywords:
        return None
    if _attribute_chain(node.func) != ("importlib", "metadata", "version"):
        return None
    value = node.args[0]
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None


def _dependency_threshold(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Version" and len(node.args) == 1 and not node.keywords:
        value = node.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return None


def _branch_imports(statements: list[ast.stmt]) -> tuple[str, ...] | None:
    if not statements:
        return None
    imports: list[str] = []
    for statement in statements:
        if isinstance(statement, ast.Import):
            imports.extend(alias.name for alias in statement.names)
        elif isinstance(statement, ast.ImportFrom) and statement.module is not None:
            imports.extend(f"{statement.module}.{alias.name}" for alias in statement.names)
    return tuple(imports) if imports else None


def _attribute_chain(node: ast.expr) -> tuple[str, ...]:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return ()
    parts.append(current.id)
    return tuple(reversed(parts))


def _span(node: ast.AST) -> SourceSpan:
    return SourceSpan(node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)


def _span_for_statements(statements: list[ast.stmt]) -> SourceSpan:
    return SourceSpan(
        statements[0].lineno, statements[0].col_offset,
        statements[-1].end_lineno, statements[-1].end_col_offset,
    )


def _source(source: str, node: ast.AST) -> str:
    return ast.get_source_segment(source, node) or ast.unparse(node)


def _candidate_id(head: str, path: str, discovery: _DiscoveredCompatibility) -> str:
    identity = "\0".join(
        (
            COMPATIBILITY_SCHEMA_VERSION, head, path, discovery.candidate_kind,
            str(discovery.line), str(discovery.column), discovery.subject or "",
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"sunset-compat-v{COMPATIBILITY_SCHEMA_VERSION}-{digest}"
