"""G29 — provenance-integrity guard over candidate review packets."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from sunset.blame_evidence import RecordedBlameProvider
from sunset.provenance_integrity import (
    ProvenanceRecord,
    find_shared_commit_groups,
    verify_review_packet,
)

PACKET = Path("tests/fixtures/public_corpus/openclaw-g27-pilot-review-v1.json")
BLAME = Path("tests/fixtures/blame_evidence/openclaw-g27-blame-v1.json")
SPURIOUS = "ad6a81d540d899ca52f8eaabb42fdd87cd893ec3"


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_corrected_packet_verifies_clean() -> None:
    check = verify_review_packet(_packet(), RecordedBlameProvider(BLAME))
    assert check.ok
    assert check.verified_count == check.record_count == 4
    assert check.issues == ()


def test_spurious_shared_commit_is_rejected() -> None:
    packet = _packet()
    for candidate in packet["candidates"]:
        candidate["introducing_commit"] = SPURIOUS
    check = verify_review_packet(packet, RecordedBlameProvider(BLAME))
    assert not check.ok
    kinds = {issue.kind for issue in check.issues}
    assert "provenance_mismatch" in kinds
    assert "unverified_shared_commit" in kinds
    # every candidate is flagged as a mismatch
    mismatches = [i for i in check.issues if i.kind == "provenance_mismatch"]
    assert len(mismatches) == 4


def test_single_wrong_commit_is_flagged() -> None:
    packet = _packet()
    packet["candidates"][0]["introducing_commit"] = "0" * 40
    check = verify_review_packet(packet, RecordedBlameProvider(BLAME))
    assert not check.ok
    assert check.verified_count == 3
    assert any(i.kind == "provenance_mismatch" for i in check.issues)


def test_unverifiable_when_blame_missing() -> None:
    packet = _packet()
    packet["candidates"][0]["line"] = 99999  # not in the blame fixture
    check = verify_review_packet(packet, RecordedBlameProvider(BLAME))
    assert not check.ok
    assert any(i.kind == "unverifiable_provenance" for i in check.issues)


def test_find_shared_commit_groups_ignores_same_file() -> None:
    same_file = (
        ProvenanceRecord("a", "x.ts", 1, "c" * 40),
        ProvenanceRecord("b", "x.ts", 2, "c" * 40),
    )
    assert find_shared_commit_groups(same_file) == {}

    distinct = (
        ProvenanceRecord("a", "x.ts", 1, "c" * 40),
        ProvenanceRecord("b", "y.ts", 1, "c" * 40),
    )
    groups = find_shared_commit_groups(distinct)
    assert groups == {"c" * 40: {"x.ts", "y.ts"}}


def test_legitimate_verified_sharing_is_allowed(tmp_path: Path) -> None:
    # Two distinct files whose lines are genuinely introduced by one commit,
    # and the blame fixture verifies both -> no issue.
    commit = "1234567890abcdef1234567890abcdef12345678"
    fixture = {
        "schema_version": "1",
        "responses": [
            {"repository_url": "https://github.com/o/r", "commit_sha": "a" * 40, "path": "x.ts", "line": 1, "outcome": "complete", "introducing_commit": commit},
            {"repository_url": "https://github.com/o/r", "commit_sha": "a" * 40, "path": "y.ts", "line": 1, "outcome": "complete", "introducing_commit": commit},
        ],
    }
    fixture_path = tmp_path / "blame.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    packet = {
        "repository_url": "https://github.com/o/r",
        "repository_head": "a" * 40,
        "candidates": [
            {"candidate_id": "c1", "path": "x.ts", "line": 1, "introducing_commit": commit},
            {"candidate_id": "c2", "path": "y.ts", "line": 1, "introducing_commit": commit},
        ],
    }
    check = verify_review_packet(packet, RecordedBlameProvider(fixture_path))
    assert check.ok
    assert check.verified_count == 2
