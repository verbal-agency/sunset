"""Offline validation for saved, reproducible public release evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


_FULL_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


class ReleaseEvidenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_public_run(path: str | Path) -> dict[str, Any]:
    """Validate a saved public run and the exact outputs it references."""

    manifest_path = Path(path).expanduser().resolve()
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseEvidenceError("public_run_unreadable", str(exc)) from exc
    if not isinstance(value, dict) or value.get("schema_version") != "1":
        raise ReleaseEvidenceError("public_run_schema_invalid", "public run must use schema version 1")

    repository = _mapping(value, "repository")
    head = repository.get("pinned_head")
    url = repository.get("url")
    if not isinstance(head, str) or _FULL_SHA.fullmatch(head) is None:
        raise ReleaseEvidenceError("public_run_head_invalid", "repository pinned_head must be a full Git SHA")
    if not isinstance(url, str) or not url.startswith("https://github.com/") or not url.endswith(".git"):
        raise ReleaseEvidenceError("public_run_url_invalid", "repository URL must be a canonical HTTPS GitHub clone URL")

    safety = _mapping(value, "safety")
    if safety.get("target_code_installed") is not False or safety.get("target_code_executed") is not False:
        raise ReleaseEvidenceError("public_run_execution_unsafe", "public run must not install or execute target code")
    if safety.get("working_tree_before") != "clean" or safety.get("working_tree_after") != "clean":
        raise ReleaseEvidenceError("public_run_target_dirty", "public run must record a clean target before and after")
    if safety.get("tree_before") != safety.get("tree_after"):
        raise ReleaseEvidenceError("public_run_target_changed", "target Git tree changed during the public run")

    results = value.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise ReleaseEvidenceError("public_run_results_invalid", "public run requires scan and investigation results")
    by_kind: dict[str, dict[str, Any]] = {}
    for result in results:
        if not isinstance(result, dict) or result.get("kind") not in {"scan", "investigation"}:
            raise ReleaseEvidenceError("public_run_result_invalid", "unsupported public result kind")
        kind = str(result["kind"])
        if kind in by_kind:
            raise ReleaseEvidenceError("public_run_result_duplicate", f"duplicate {kind} result")
        command = result.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            raise ReleaseEvidenceError("public_run_command_invalid", f"{kind} command must be an argv list")
        by_kind[kind] = result

    scan_payload = _verified_output(manifest_path, by_kind["scan"])
    investigation_payload = _verified_output(manifest_path, by_kind["investigation"])
    candidates = scan_payload.get("candidates")
    if (
        by_kind["scan"].get("status") != "success"
        or scan_payload.get("schema_version") != "1"
        or scan_payload.get("repository_head") != head
        or not isinstance(candidates, list)
        or not candidates
        or scan_payload.get("errors") != []
    ):
        raise ReleaseEvidenceError("public_run_scan_invalid", "saved scan is not a successful pinned discovery result")
    candidate_ids = {item.get("candidate_id") for item in candidates if isinstance(item, dict)}
    if (
        by_kind["investigation"].get("status") != "inconclusive"
        or investigation_payload.get("schema_version") != "2"
        or investigation_payload.get("repository_head") != head
        or investigation_payload.get("status") != "inconclusive"
        or investigation_payload.get("assumption_status") != "unknown"
        or investigation_payload.get("candidate_id") not in candidate_ids
        or investigation_payload.get("errors") != []
    ):
        raise ReleaseEvidenceError("public_run_investigation_invalid", "saved investigation is not a clean pinned inconclusive result")
    return value


def _mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ReleaseEvidenceError("public_run_field_invalid", f"{key} must be an object")
    return item


def _verified_output(manifest_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    relative = result.get("output")
    expected = result.get("sha256")
    if not isinstance(relative, str) or not isinstance(expected, str) or _DIGEST.fullmatch(expected) is None:
        raise ReleaseEvidenceError("public_run_output_invalid", "result output and SHA-256 digest are required")
    output_path = (manifest_path.parent / relative).resolve()
    try:
        output_path.relative_to(manifest_path.parent)
    except ValueError as exc:
        raise ReleaseEvidenceError("public_run_output_unsafe", "result output escapes the release directory") from exc
    try:
        data = output_path.read_bytes()
        payload = json.loads(data)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseEvidenceError("public_run_output_unreadable", str(exc)) from exc
    if hashlib.sha256(data).hexdigest() != expected:
        raise ReleaseEvidenceError("public_run_output_digest_mismatch", f"digest mismatch for {relative}")
    if not isinstance(payload, dict):
        raise ReleaseEvidenceError("public_run_output_invalid", f"{relative} must contain a JSON object")
    return payload
