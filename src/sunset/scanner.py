"""AST-based discovery of pytest skip and expected-failure markers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
from pathlib import Path

from sunset.git_repository import GitRepository, RepositoryError
from sunset.models import Candidate, SCHEMA_VERSION, ScanError, ScanResult


SUPPORTED_MARKERS = frozenset({"skip", "skipif", "xfail"})


@dataclass(frozen=True, slots=True)
class _DiscoveredMarker:
    marker_kind: str
    line: int
    column: int
    qualified_name: str
    reason: str | None
    condition: str | None


class _MarkerVisitor(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.source = source
        self.class_names: list[str] = []
        self.markers: list[_DiscoveredMarker] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not node.name.startswith("Test"):
            return
        self._record_decorators(node, node.name)
        self.class_names.append(node.name)
        for child in node.body:
            self.visit(child)
        self.class_names.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if not node.name.startswith("test"):
            return
        qualified_name = ".".join([*self.class_names, node.name])
        self._record_decorators(node, qualified_name)

    def _record_decorators(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        qualified_name: str,
    ) -> None:
        for decorator in node.decorator_list:
            marker = _parse_decorator(decorator, self.source, qualified_name)
            if marker is not None:
                self.markers.append(marker)


def scan_repository(target: str | Path) -> ScanResult:
    """Scan the committed HEAD below *target* without touching the working tree."""

    repository = GitRepository.open(target)
    candidates: list[Candidate] = []
    errors: list[ScanError] = []

    for path in repository.list_test_files():
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
                    kind="parse_error",
                    path=path,
                    message=exc.msg,
                    line=exc.lineno,
                    column=exc.offset,
                )
            )
            continue

        visitor = _MarkerVisitor(source)
        visitor.visit(tree)
        for marker in visitor.markers:
            try:
                blame_commit = repository.blame_commit(path, marker.line)
            except RepositoryError as exc:
                errors.append(
                    ScanError(
                        kind=exc.code,
                        path=path,
                        message=exc.message,
                        line=marker.line,
                        column=marker.column,
                    )
                )
                continue

            candidates.append(
                Candidate(
                    candidate_id=_candidate_id(repository.head, path, marker),
                    marker_kind=marker.marker_kind,
                    path=path,
                    line=marker.line,
                    column=marker.column,
                    qualified_name=marker.qualified_name,
                    reason=marker.reason,
                    condition=marker.condition,
                    repository_head=repository.head,
                    blame_commit=blame_commit,
                )
            )

    candidates.sort(
        key=lambda item: (
            item.path,
            item.line,
            item.column,
            item.marker_kind,
            item.qualified_name,
        )
    )
    errors.sort(
        key=lambda item: (
            item.path,
            item.line if item.line is not None else -1,
            item.column if item.column is not None else -1,
            item.kind,
        )
    )
    return ScanResult(
        repository_head=repository.head,
        candidates=tuple(candidates),
        errors=tuple(errors),
    )


def _parse_decorator(
    decorator: ast.expr,
    source: str,
    qualified_name: str,
) -> _DiscoveredMarker | None:
    call = decorator if isinstance(decorator, ast.Call) else None
    target = call.func if call is not None else decorator
    chain = _attribute_chain(target)
    if len(chain) != 3 or chain[:2] != ("pytest", "mark"):
        return None

    marker_kind = chain[2]
    if marker_kind not in SUPPORTED_MARKERS:
        return None

    reason = None
    condition = None
    if call is not None:
        reason_node = _keyword_value(call, "reason")
        if isinstance(reason_node, ast.Constant) and isinstance(reason_node.value, str):
            reason = reason_node.value

        condition_node = None
        if marker_kind in {"skipif", "xfail"}:
            condition_node = call.args[0] if call.args else _keyword_value(call, "condition")
        if condition_node is not None:
            condition = ast.get_source_segment(source, condition_node)
            if condition is None:
                condition = ast.unparse(condition_node)

    source_line = source.splitlines()[decorator.lineno - 1]
    decorator_column = source_line.find("@")
    if decorator_column < 0:
        decorator_column = decorator.col_offset

    return _DiscoveredMarker(
        marker_kind=marker_kind,
        line=decorator.lineno,
        column=decorator_column,
        qualified_name=qualified_name,
        reason=reason,
        condition=condition,
    )


def _attribute_chain(node: ast.expr) -> tuple[str, ...]:
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    else:
        return ()
    return tuple(reversed(parts))


def _keyword_value(call: ast.Call, name: str) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _candidate_id(head: str, path: str, marker: _DiscoveredMarker) -> str:
    identity = "\0".join(
        (
            SCHEMA_VERSION,
            head,
            path,
            marker.qualified_name,
            marker.marker_kind,
            str(marker.line),
            str(marker.column),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"sunset-v{SCHEMA_VERSION}-{digest}"
