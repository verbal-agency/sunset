"""Provenance-integrity checks for candidate review packets.

The G27 pilot review packet recorded an identical, unrelated ``introducing_commit``
for four distinct candidates. These checks catch that class of defect: they verify
each recorded commit against an authenticated exact-SHA blame source (G28), and
flag any commit shared across distinct files that is not individually verified.

Legitimate sharing (several lines of one file introduced by one commit) is not
flagged; the smell is distinct files claiming the same introduction point without
verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sunset.blame_evidence import BlameProvider
from sunset.blame_evidence_models import BlameRequest


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    candidate_id: str
    path: str
    line: int
    introducing_commit: str | None


@dataclass(frozen=True, slots=True)
class ProvenanceIssue:
    kind: str
    candidate_id: str
    path: str
    line: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "candidate_id": self.candidate_id,
            "path": self.path,
            "line": self.line,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ProvenanceCheck:
    ok: bool
    verified_count: int
    record_count: int
    issues: tuple[ProvenanceIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "verified_count": self.verified_count,
            "record_count": self.record_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def records_from_review_packet(packet: dict[str, Any]) -> tuple[ProvenanceRecord, ...]:
    records: list[ProvenanceRecord] = []
    for candidate in packet.get("candidates", []):
        records.append(
            ProvenanceRecord(
                candidate_id=str(candidate.get("candidate_id", "")),
                path=str(candidate.get("path", "")),
                line=int(candidate.get("line", 0)),
                introducing_commit=candidate.get("introducing_commit"),
            )
        )
    return tuple(records)


def find_shared_commit_groups(records: tuple[ProvenanceRecord, ...]) -> dict[str, set[str]]:
    """Map each introducing_commit to the set of distinct paths that claim it."""

    groups: dict[str, set[str]] = {}
    for record in records:
        if record.introducing_commit:
            groups.setdefault(record.introducing_commit, set()).add(record.path)
    return {commit: paths for commit, paths in groups.items() if len(paths) > 1}


def verify_review_packet(packet: dict[str, Any], provider: BlameProvider) -> ProvenanceCheck:
    """Verify each recorded introducing_commit against authenticated blame."""

    repository_url = str(packet.get("repository_url", "")).removesuffix(".git")
    head = str(packet.get("repository_head", ""))
    records = records_from_review_packet(packet)
    issues: list[ProvenanceIssue] = []
    verified: set[str] = set()

    for record in records:
        response = provider.blame(BlameRequest(record.candidate_id, repository_url, head, record.path, record.line))
        if response.outcome != "complete" or response.introducing_commit is None:
            issues.append(ProvenanceIssue("unverifiable_provenance", record.candidate_id, record.path, record.line, f"blame outcome was {response.outcome}"))
            continue
        if record.introducing_commit != response.introducing_commit:
            issues.append(
                ProvenanceIssue(
                    "provenance_mismatch",
                    record.candidate_id,
                    record.path,
                    record.line,
                    f"recorded {record.introducing_commit!r} but authenticated blame gives {response.introducing_commit!r}",
                )
            )
            continue
        verified.add(record.candidate_id)

    for commit, paths in find_shared_commit_groups(records).items():
        shared = [record for record in records if record.introducing_commit == commit]
        if not all(record.candidate_id in verified for record in shared):
            for record in shared:
                issues.append(
                    ProvenanceIssue(
                        "unverified_shared_commit",
                        record.candidate_id,
                        record.path,
                        record.line,
                        f"commit {commit} is claimed by {len(paths)} distinct files without full verification",
                    )
                )

    issues.sort(key=lambda item: (item.path, item.line, item.kind, item.candidate_id))
    return ProvenanceCheck(not issues, len(verified), len(records), tuple(issues))


__all__ = [
    "ProvenanceCheck",
    "ProvenanceIssue",
    "ProvenanceRecord",
    "find_shared_commit_groups",
    "records_from_review_packet",
    "verify_review_packet",
]
