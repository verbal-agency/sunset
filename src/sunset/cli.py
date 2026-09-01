"""Command-line interface for Sunset's deterministic scanner."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import shlex
import sys

from sunset.casefile import build_case_file
from sunset.casefile_models import CaseFileError
from sunset.benchmark import (
    BenchmarkError,
    evaluate_corpus,
    langsmith_export,
    load_corpus,
    publish_langsmith_export,
)
from sunset.git_repository import RepositoryError
from sunset.models import ScanError, ScanResult
from sunset.compatibility import scan_compatibility_repository
from sunset.compatibility_models import CompatibilityScanResult
from sunset.investigation import InvestigationConfig, investigate_candidate
from sunset.investigation_models import InvestigationError, InvestigationResult, TokenBaseline
from sunset.provenance import collect_compatibility_provenance, collect_provenance
from sunset.provenance_models import ProvenanceError, ProvenanceResult
from sunset.public_corpus import PublicCorpusError, PublicCorpusReport, load_public_corpus
from sunset.validation_corpus import ValidationCorpusError, audit_validation_corpus, load_validation_corpus
from sunset.release import ReleaseEvidenceError, validate_public_run
from sunset.scanner import scan_repository
from sunset.validation import ValidationConfig, validate_candidate
from sunset.validation_models import ValidationError, ValidationResult
from sunset import __version__
from sunset.agent_tools import tool_catalog_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sunset",
        description="Conservatively investigate code whose original rationale may have expired.",
    )
    parser.add_argument("--version", action="version", version=f"sunset {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    tools_parser = subparsers.add_parser(
        "tools",
        help="list the local read-only agent tool contracts",
    )
    tools_parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="output format (default: json)",
    )
    scan_parser = subparsers.add_parser(
        "scan",
        help="scan a committed Git snapshot for supported pytest markers",
    )
    scan_parser.add_argument("repository", help="repository root or subdirectory")
    scan_parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="output format (default: json)",
    )
    collect_parser = subparsers.add_parser(
        "collect",
        help="collect a selected non-test deterministic candidate family",
    )
    collect_parser.add_argument("repository", help="repository root or subdirectory")
    collect_parser.add_argument(
        "--collector", choices=("compatibility",), default="compatibility",
        help="collector family (default: compatibility)",
    )
    collect_parser.add_argument(
        "--format", choices=("json",), default="json", help="output format (default: json)"
    )
    provenance_parser = subparsers.add_parser(
        "provenance",
        help="collect local Git provenance into an external artifact store",
    )
    provenance_parser.add_argument("repository", help="repository root or subdirectory")
    provenance_parser.add_argument(
        "--collector", choices=("pytest", "compatibility"), default="pytest",
        help="candidate family whose local Git evidence is collected (default: pytest)",
    )
    investigate_parser = subparsers.add_parser(
        "investigate",
        help="run or resume one bounded rationale investigation",
    )
    investigate_parser.add_argument("repository", help="repository root or subdirectory")
    investigate_parser.add_argument("--candidate-id", required=True, help="candidate ID from scan or collect")
    investigate_parser.add_argument(
        "--collector", choices=("pytest", "compatibility"), default="pytest",
        help="candidate family (default: pytest)",
    )
    investigate_parser.add_argument("--store", required=True, help="external artifact and checkpoint store")
    investigate_parser.add_argument("--interrupt-after", choices=("load_provenance", "retrieve_core", "summarize_core", "expand_history", "verify_external", "finalize"))
    investigate_parser.add_argument("--max-input-tokens", type=int, default=100_000)
    investigate_parser.add_argument("--max-output-tokens", type=int, default=8_000)
    investigate_parser.add_argument(
        "--evidence-mode", choices=("offline", "recorded", "live"), default="offline",
        help="external evidence mode; offline makes no requests (default: offline)",
    )
    investigate_parser.add_argument(
        "--recorded-evidence", metavar="FIXTURE.json",
        help="recorded provider fixture; required for --evidence-mode recorded",
    )
    investigate_parser.add_argument("--format", choices=("json",), default="json")
    validate_parser = subparsers.add_parser(
        "validate",
        help="run an approved marker-removal experiment in a disposable clone",
    )
    validate_parser.add_argument("repository", help="repository root or subdirectory")
    validate_parser.add_argument("--candidate-id", required=True, help="pytest candidate ID from scan")
    validate_parser.add_argument("--store", required=True, help="external artifact store")
    validate_parser.add_argument(
        "--collector", choices=("pytest", "compatibility"), default="pytest",
        help="candidate family; only pytest is currently supported",
    )
    validate_parser.add_argument("--approve", action="store_true", help="explicitly approve clone-only marker removal and test execution")
    validate_parser.add_argument("--repeat", type=int, default=2, help="narrow-test repetitions (default: 2)")
    validate_parser.add_argument("--timeout-seconds", type=int, default=60)
    validate_parser.add_argument(
        "--broader-command", action="append", default=[], metavar="COMMAND",
        help="optional shell-free command to run in the disposable clone; repeatable",
    )
    validate_parser.add_argument("--format", choices=("json",), default="json")
    casefile_parser = subparsers.add_parser(
        "casefile",
        help="render a citation-verified, read-only case file from saved results",
    )
    casefile_parser.add_argument(
        "--investigation-result", required=True, metavar="INVESTIGATION.json",
        help="saved JSON emitted by sunset investigate",
    )
    casefile_parser.add_argument(
        "--validation-result", metavar="VALIDATION.json",
        help="optional saved JSON emitted by sunset validate",
    )
    casefile_parser.add_argument("--store", required=True, help="external artifact store to verify")
    casefile_parser.add_argument(
        "--format", choices=("json", "markdown", "html"), default="json",
        help="output format; HTML is a passive standalone viewer",
    )
    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="evaluate a saved compact-memory benchmark corpus without rerunning repositories",
    )
    benchmark_parser.add_argument("--corpus", required=True, help="versioned benchmark corpus JSON")
    benchmark_parser.add_argument("--format", choices=("json", "markdown"), default="json")
    benchmark_parser.add_argument(
        "--langsmith-export", metavar="FILE.json",
        help="write a data-only LangSmith experiment export",
    )
    benchmark_parser.add_argument(
        "--publish-langsmith", action="store_true",
        help="explicitly POST the export to LangSmith; requires --langsmith-api-key",
    )
    benchmark_parser.add_argument("--langsmith-api-key", help="LangSmith API key used only with --publish-langsmith")
    corpus_parser = subparsers.add_parser("corpus", help="validate a saved public corpus without contacting target repositories")
    corpus_parser.add_argument("--manifest", required=True, help="saved public corpus JSON")
    validation_corpus_parser = subparsers.add_parser(
        "validation-corpus", help="audit a provenance-bound validation corpus offline"
    )
    validation_corpus_subparsers = validation_corpus_parser.add_subparsers(dest="validation_corpus_command", required=True)
    validation_audit_parser = validation_corpus_subparsers.add_parser("audit", help="audit a saved validation corpus")
    validation_audit_parser.add_argument("--manifest", required=True, help="saved validation corpus JSON")
    validation_audit_parser.add_argument("--output", help="optional path for the JSON audit report")
    validation_audit_parser.add_argument("--max-cases", type=int, help="optional positive case-processing budget")
    release_parser = subparsers.add_parser(
        "release-check", help="validate saved public-release evidence and immutable output digests"
    )
    release_parser.add_argument("--manifest", required=True, help="saved public-run manifest JSON")
    provenance_parser.add_argument(
        "--store",
        required=True,
        help="external directory used for content-addressed artifacts",
    )
    provenance_parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="output format (default: json)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "tools":
        sys.stdout.write(tool_catalog_json())
        return 0

    if args.command == "scan":
        try:
            result = scan_repository(args.repository)
        except RepositoryError as exc:
            result = ScanResult(
                repository_head=None,
                errors=(
                    ScanError(
                        kind=exc.code,
                        path=".",
                        message=exc.message,
                    ),
                ),
            )
            sys.stdout.write(result.to_json())
            return 2

        sys.stdout.write(result.to_json())
        return 1 if result.errors else 0

    if args.command == "collect":
        try:
            result = scan_compatibility_repository(args.repository)
        except RepositoryError as exc:
            result = CompatibilityScanResult(
                repository_head=None,
                errors=(ScanError(kind=exc.code, path=".", message=exc.message),),
            )
            sys.stdout.write(result.to_json())
            return 2
        sys.stdout.write(result.to_json())
        return 1 if result.errors else 0

    if args.command == "provenance":
        try:
            collector = collect_provenance if args.collector == "pytest" else collect_compatibility_provenance
            result = collector(args.repository, store_path=args.store)
        except RepositoryError as exc:
            result = ProvenanceResult(
                candidates=(),
                errors=(
                    ProvenanceError(
                        kind=exc.code,
                        message=exc.message,
                        path=".",
                    ),
                ),
                repository_head=None,
                repository_identity_kind=None,
                repository_identity_value=None,
            )
            sys.stdout.write(result.to_json())
            return 2

        sys.stdout.write(result.to_json())
        return 1 if result.errors else 0

    if args.command == "investigate":
        try:
            result = investigate_candidate(
                args.repository,
                store_path=args.store,
                candidate_id=args.candidate_id,
                collector=args.collector,
                config=InvestigationConfig(
                    max_input_tokens=args.max_input_tokens,
                    max_output_tokens=args.max_output_tokens,
                    interrupt_after=args.interrupt_after,
                    evidence_mode=args.evidence_mode,
                    recorded_fixture_path=args.recorded_evidence,
                ),
            )
        except RepositoryError as exc:
            result = InvestigationResult(
                assumption_status="unknown",
                candidate_id=args.candidate_id,
                checkpoint_id="",
                collector=args.collector,
                errors=(InvestigationError(kind=exc.code, message=exc.message),),
                ledger=(),
                open_questions=(),
                repository_head="",
                run_id="",
                selected_evidence=(),
                status="error",
                token_baseline=TokenBaseline(0, 0, 0),
                token_usage=(),
            )
            sys.stdout.write(result.to_json())
            return 2
        sys.stdout.write(result.to_json())
        return 0 if result.status == "inconclusive" else 1

    if args.command == "validate":
        try:
            commands = tuple(tuple(shlex.split(value)) for value in args.broader_command)
            result = validate_candidate(
                args.repository,
                store_path=args.store,
                candidate_id=args.candidate_id,
                approved=args.approve,
                collector=args.collector,
                config=ValidationConfig(
                    repeat_count=args.repeat,
                    broader_commands=commands,
                    timeout_seconds=args.timeout_seconds,
                ),
            )
        except RepositoryError as exc:
            result = ValidationResult(
                approved=args.approve,
                candidate_id=args.candidate_id,
                collector=args.collector,
                environment=None,
                errors=(ValidationError(exc.code, exc.message),),
                repository_head="",
                runs=(),
                status="inconclusive",
            )
            sys.stdout.write(result.to_json())
            return 2
        except ValueError as exc:
            result = ValidationResult(
                approved=args.approve,
                candidate_id=args.candidate_id,
                collector=args.collector,
                environment=None,
                errors=(ValidationError("invalid_validation_config", str(exc)),),
                repository_head="",
                runs=(),
                status="inconclusive",
            )
            sys.stdout.write(result.to_json())
            return 2
        sys.stdout.write(result.to_json())
        return 0 if result.status in {"confirmed", "still_failing", "flaky", "inconclusive"} else 1

    if args.command == "casefile":
        try:
            investigation = InvestigationResult.from_dict(_load_saved_json(args.investigation_result))
            validation = None
            if args.validation_result:
                validation = ValidationResult.from_dict(_load_saved_json(args.validation_result))
            result = build_case_file(
                investigation,
                validation=validation,
                store_path=args.store,
            )
        except (CaseFileError, KeyError, TypeError, ValueError, json.JSONDecodeError, OSError) as exc:
            if isinstance(exc, CaseFileError):
                error = exc.to_dict()
            else:
                error = {"kind": "saved_result_invalid", "message": str(exc)}
            sys.stdout.write(json.dumps({"error": error}, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            return 2
        if args.format == "markdown":
            rendered = result.to_markdown()
        elif args.format == "html":
            rendered = result.to_html()
        else:
            rendered = result.to_json()
        sys.stdout.write(rendered)
        return 0

    if args.command == "benchmark":
        try:
            corpus = load_corpus(args.corpus)
            result = evaluate_corpus(corpus)
            export = langsmith_export(corpus, result)
            if args.langsmith_export:
                Path(args.langsmith_export).write_text(
                    json.dumps(export, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            if args.publish_langsmith:
                publish_langsmith_export(export, api_key=args.langsmith_api_key or "")
        except (BenchmarkError, OSError) as exc:
            error = {"kind": exc.code, "message": exc.message} if isinstance(exc, BenchmarkError) else {
                "kind": "benchmark_output_failed", "message": str(exc)
            }
            sys.stdout.write(json.dumps({"error": error}, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            return 2
        sys.stdout.write(result.to_markdown() if args.format == "markdown" else result.to_json())
        return 0

    if args.command == "corpus":
        try:
            result = PublicCorpusReport(load_public_corpus(args.manifest))
        except (PublicCorpusError, OSError) as exc:
            error = {"kind": exc.code, "message": exc.message} if isinstance(exc, PublicCorpusError) else {"kind": "public_corpus_read_failed", "message": str(exc)}
            sys.stdout.write(json.dumps({"error": error}, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            return 2
        sys.stdout.write(result.to_json())
        return 0

    if args.command == "validation-corpus":
        try:
            result = audit_validation_corpus(
                load_validation_corpus(args.manifest), max_cases=args.max_cases
            )
            rendered = result.to_json()
            if args.output:
                Path(args.output).write_text(rendered, encoding="utf-8")
        except (ValidationCorpusError, OSError) as exc:
            error = {"kind": exc.code, "message": exc.message} if isinstance(exc, ValidationCorpusError) else {
                "kind": "validation_corpus_output_failed", "message": str(exc)
            }
            sys.stdout.write(json.dumps({"error": error}, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            return 2
        sys.stdout.write(rendered)
        return 0

    if args.command == "release-check":
        try:
            manifest = validate_public_run(args.manifest)
        except ReleaseEvidenceError as exc:
            sys.stdout.write(json.dumps({"error": {"kind": exc.code, "message": exc.message}}, indent=2, sort_keys=True) + "\n")
            return 2
        sys.stdout.write(
            json.dumps(
                {
                    "repository": manifest["repository"],
                    "result_statuses": {
                        item["kind"]: item["status"] for item in manifest["results"]
                    },
                    "schema_version": manifest["schema_version"],
                    "valid": True,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n"
        )
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


def entrypoint() -> None:
    raise SystemExit(main())


def _load_saved_json(path: str) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("saved result must be a JSON object")
    return value
