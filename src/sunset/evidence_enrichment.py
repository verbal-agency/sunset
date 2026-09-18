"""Assemble richer static evidence for a marker before the agent judges it.

Thin evidence (a marker's reason + the package version) leaves the agent
guessing. This module composes the fuller context a triaging maintainer would
actually see — the test's own source and the marker's introduction (blame) — into
one evidence string for the G30 live reasoner.

Important, measured caveat (see docs/research/G30-evidence-enrichment-v1.md): on
langchain-core this richer static evidence did **not** reliably improve the agent's
condition judgment. The decisive signal is whether the code under test *currently*
behaves as asserted, which static text does not contain — only executing the clone
reveals it. Enrichment sharpens the agent's input; it does not replace empirical
adjudication.

The AST extraction and evidence composition here are pure and offline-testable.
Blame is passed in as a string by the caller (it is environment-specific), so this
module never shells out.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarkerSource:
    function: str
    reason: str | None
    xfail_line: int | None
    source: str


def _is_xfail(node: ast.expr) -> bool:
    target = node.func if isinstance(node, ast.Call) else node
    return isinstance(target, ast.Attribute) and target.attr == "xfail"


def _reason(dec: ast.expr) -> str | None:
    if isinstance(dec, ast.Call):
        for kw in dec.keywords:
            if kw.arg == "reason" and isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
    return None


def extract_marker_source(source_text: str, function_name: str) -> MarkerSource | None:
    """Find an xfail-marked test function and return its reason, decorator line, and source."""

    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            xfail_line: int | None = None
            reason: str | None = None
            for dec in node.decorator_list:
                if _is_xfail(dec):
                    xfail_line = dec.lineno
                    reason = _reason(dec)
            body = ast.get_source_segment(source_text, node) or ""
            return MarkerSource(function=function_name, reason=reason, xfail_line=xfail_line, source=body)
    return None


def build_enriched_evidence(
    *,
    package: str,
    version: str,
    node: str,
    marker: MarkerSource,
    blame: str | None = None,
    max_source_chars: int = 1600,
) -> str:
    """Compose reason + version + blame + test source into one evidence string."""

    lines = [
        f"Package: {package} {version}.",
        f"Test: {node}, marked @pytest.mark.xfail(reason={marker.reason!r}).",
    ]
    if blame:
        lines.append(f"Marker introduced by: {blame}.")
    lines.append("An xfail marker means the test is expected to fail; the reason states why.")
    lines.append("Full test source:")
    lines.append(marker.source[:max_source_chars])
    lines.append("Judge whether the protected condition behind this marker is still in force.")
    return "\n".join(lines)


__all__ = ["MarkerSource", "build_enriched_evidence", "extract_marker_source"]
