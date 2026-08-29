"""Command-line interface for Sunset's deterministic scanner."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys

from sunset.git_repository import RepositoryError
from sunset.models import ScanError, ScanResult
from sunset.compatibility import scan_compatibility_repository
from sunset.compatibility_models import CompatibilityScanResult
from sunset.investigation import InvestigationConfig, investigate_candidate
from sunset.investigation_models import InvestigationError, InvestigationResult, TokenBaseline
from sunset.provenance import collect_compatibility_provenance, collect_provenance
from sunset.provenance_models import ProvenanceError, ProvenanceResult
from sunset.scanner import scan_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sunset",
        description="Find pytest markers whose rationale may warrant investigation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
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
        help="run or resume one bounded local-only rationale investigation",
    )
    investigate_parser.add_argument("repository", help="repository root or subdirectory")
    investigate_parser.add_argument("--candidate-id", required=True, help="candidate ID from scan or collect")
    investigate_parser.add_argument(
        "--collector", choices=("pytest", "compatibility"), default="pytest",
        help="candidate family (default: pytest)",
    )
    investigate_parser.add_argument("--store", required=True, help="external artifact and checkpoint store")
    investigate_parser.add_argument("--interrupt-after", choices=("load_provenance", "retrieve_core", "summarize_core", "expand_history", "finalize"))
    investigate_parser.add_argument("--max-input-tokens", type=int, default=100_000)
    investigate_parser.add_argument("--max-output-tokens", type=int, default=8_000)
    investigate_parser.add_argument("--format", choices=("json",), default="json")
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
                ),
            )
        except RepositoryError as exc:
            result = InvestigationResult(
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

    raise AssertionError(f"unhandled command: {args.command}")


def entrypoint() -> None:
    raise SystemExit(main())
