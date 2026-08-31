from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.cli import main
from sunset.public_corpus import PublicCorpusError, load_public_corpus


CORPUS_PATH = Path(__file__).parent / "fixtures" / "public_corpus" / "langchain-ecosystem-v1.json"


def test_public_corpus_is_pinned_balanced_and_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("manifest validation must not access a target repository")

    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    corpus = load_public_corpus(CORPUS_PATH)

    assert len(corpus.cases) == 20
    assert sum(case.observed_outcome == "removed" for case in corpus.cases) == 10
    assert sum(case.observed_outcome == "retained" for case in corpus.cases) == 10
    assert {case.collection_mode for case in corpus.cases} == {"public_git_read_only"}


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("case_id", "lc-stale-xfail", "public_corpus_case_ids_not_unique"),
        ("source_commit", "94509faa", "public_corpus_sha_invalid"),
        ("path", "", "public_corpus_path_invalid"),
        ("repository_url", "https://github.com/langchain-ai/langchain", "public_corpus_repository_unpinned"),
        ("evidence_url", "https://github.com/langchain-ai/langchain/commit/deadbeef", "public_corpus_evidence_invalid"),
    ],
)
def test_public_corpus_rejects_malformed_records(
    tmp_path: Path, field: str, value: str, code: str
) -> None:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    payload["cases"][1][field] = value
    malformed = tmp_path / "malformed.json"
    malformed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PublicCorpusError) as exc_info:
        load_public_corpus(malformed)

    assert exc_info.value.code == code


def test_public_corpus_rejects_invalid_repository_distribution(tmp_path: Path) -> None:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    payload["cases"][0]["repository"] = "langgraph"
    payload["cases"][0]["repository_url"] = "https://github.com/langchain-ai/langgraph.git"
    malformed = tmp_path / "distribution.json"
    malformed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PublicCorpusError) as exc_info:
        load_public_corpus(malformed)

    assert exc_info.value.code == "public_corpus_distribution_invalid"


def test_public_corpus_cli_reports_saved_manifest(capsys) -> None:
    exit_code = main(["corpus", "--manifest", str(CORPUS_PATH)])

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["repository_counts"] == {"langchain": 12, "langgraph": 4, "langsmith-sdk": 4}
    assert report["outcome_counts"] == {"removed": 10, "retained": 10}
