from __future__ import annotations

import argparse
from contextlib import ExitStack
from importlib.resources import as_file
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from .npi_api import fetch_npi_records, write_npi_sample_csv
from .pipeline import run_pipeline
from .storage import database_path, output_path, storage_root
from .bundled_assets import assets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run provider directory normalization, QA, duplicate detection, and exception exports."
    )
    subparsers = parser.add_subparsers(dest="command")

    fhir_parser = subparsers.add_parser('inspect-fhir', help='Inspect a saved FHIR searchset offline; no acceptance or database writes.')
    fhir_parser.add_argument('bundle', type=Path)
    fhir_parser.add_argument('--report', type=Path, help='Create a new JSON report; existing files are refused. Defaults to stdout.')

    mapping_eval = subparsers.add_parser('evaluate-mapping', help='Evaluate the frozen synthetic mapping baseline in a new root; model calls require --invoke-model and explicit server configuration.')
    mapping_eval.add_argument('--root', type=Path, required=True, help='New output/runtime directory; existing paths are refused.')
    mapping_eval.add_argument('--corpus-directory', type=Path, help='Override the bundled frozen synthetic corpus directory.')
    mapping_eval.add_argument('--invoke-model', action='store_true', help='Explicitly request at most one configured model call per frozen synthetic case, within the local lifetime budget.')

    consumer = subparsers.add_parser('consume-approved', help='Read a pinned approved contact export without opening application storage.')
    consumer.add_argument('export', type=Path)
    consumer.add_argument('--expected-version', required=True)
    consumer.add_argument('--expected-feed')
    consumer.add_argument('--sha256')
    consumer.add_argument('--report', type=Path, help='New output file; existing files are refused. Defaults to stdout.')

    operations = subparsers.add_parser('rehearse-operations', help='Run the synthetic controlled-source/no-model operations journey in a new owned directory.')
    operations.add_argument('--root', type=Path, required=True)

    run_parser = subparsers.add_parser("run", help="Run QA against a local provider-directory CSV.")
    add_run_arguments(run_parser)

    fetch_parser = subparsers.add_parser(
        "fetch-npi",
        help="Fetch a small public NPI Registry API sample, write it to CSV, and run QA.",
    )
    fetch_parser.add_argument("--city", type=str, default="Nashville")
    fetch_parser.add_argument("--state", type=str, default="TN")
    fetch_parser.add_argument("--limit", type=int, default=25)
    fetch_parser.add_argument(
        "--raw-output",
        type=Path,
        default=storage_root() / "npi_registry_sample_nashville.csv",
    )
    add_run_arguments(fetch_parser, include_input=False)

    # Backward-compatible legacy arguments: `provider-truth-layer --as-of ...`
    add_run_arguments(parser)
    return parser


def add_run_arguments(
    parser: argparse.ArgumentParser,
    include_input: bool = True,
) -> None:
    if include_input:
        parser.add_argument("--input", type=Path, help='Input CSV; defaults to the bundled synthetic sample.')
    parser.add_argument("--config", type=Path, help='QA rules; defaults to the bundled rules.')
    parser.add_argument("--output-dir", type=Path, default=output_path())
    parser.add_argument(
        "--payer-listings",
        type=Path,
        help="Optional payer-directory listing CSV; enables Phase 1 verification comparisons.",
    )
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=database_path(),
    )
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="Optional YYYY-MM-DD date for stale-record calculations.",
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == 'rehearse-operations':
        from .operations_rehearsal import rehearse
        try:
            result = rehearse(args.root)
        except (OSError, ValueError, RuntimeError) as exc:
            parser.exit(2, f'Operations rehearsal failed: {exc}\n')
        print(f"Retained synthetic operations rehearsal: {args.root / 'operations-rehearsal.json'}")
        print(f"Approved contacts: {len(result['consumer']['contacts'])}; NORTH: {result['north_status']}; held delivery, restart and restore preserved the approved consumer.")
        return
    if args.command == 'consume-approved':
        from .approved_consumer import MAX_BYTES, consume
        try:
            with args.export.open('rb') as stream:
                raw = stream.read(MAX_BYTES + 1)
            result = consume(raw, args.expected_version, expected_feed=args.expected_feed, expected_sha=args.sha256)
            rendered = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
            if args.report:
                with args.report.open('x', encoding='utf-8') as stream:
                    stream.write(rendered)
            else:
                print(rendered, end='')
        except (OSError, ValueError) as exc:
            parser.exit(2, f'Contact consumption failed: {exc}\n')
        return
    if args.command == 'evaluate-mapping':
        from .mapping_evaluation import evaluate
        try:
            report = evaluate(args.root, args.corpus_directory, invoke_model=args.invoke_model)
        except (OSError, ValueError) as exc:
            parser.exit(2, f'Mapping evaluation failed: {exc}\n')
        print(f"Retained {report['case_count']} synthetic cases; model calls attempted: {report['invocations_attempted']}; completed model cases: {report['completed_model_cases']}")
        print(f'Evaluation report: {args.root / "evaluation.json"}')
        return
    if args.command == 'inspect-fhir':
        from .fhir_intake import MAX_BYTES, parse_bundle
        try:
            with args.bundle.open('rb') as stream:
                result = parse_bundle(stream.read(MAX_BYTES + 1))
            rendered = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
            if args.report:
                with args.report.open('x', encoding='utf-8') as stream:
                    stream.write(rendered)
                print(f'Created offline interpretation report: {args.report}')
            else:
                print(rendered, end='')
        except (OSError, ValueError) as exc:
            parser.exit(2, f'FHIR inspection failed: {exc}\n')
        return
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else None
    if args.command == "fetch-npi":
        request_limit = min(max(args.limit * 4, args.limit), 200)
        records = fetch_npi_records(
            args.city,
            args.state,
            limit=args.limit,
            request_limit=request_limit,
        )
        input_csv = write_npi_sample_csv(
            records,
            args.raw_output,
            city_filter=args.city,
            state_filter=args.state,
            limit=args.limit,
        )
        print(f"fetched_records: {len(records)}")
        print(f"raw_output: {input_csv}")
        print(f"sample_records: {len(pd.read_csv(input_csv))}")
    else:
        input_csv = args.input

    # as_file keeps temporary resource materializations alive for the full read.
    with ExitStack() as stack:
        selected_input = input_csv if input_csv is not None else stack.enter_context(as_file(assets().joinpath('qa/sample_provider_directory.csv')))
        selected_rules = args.config if args.config is not None else stack.enter_context(as_file(assets().joinpath('qa/qa_rules.yml')))
        result = run_pipeline(
            selected_input,
            selected_rules,
            args.output_dir,
            args.sqlite,
            as_of=as_of,
            payer_listings_csv=args.payer_listings,
        )
    summary = {row["metric"]: row["value"] for _, row in result.summary.iterrows()}
    print("Provider Directory Truth Layer run complete")
    print(f"records: {summary.get('total_records', 0)}")
    print(f"records_with_issues: {summary.get('records_with_issues', 0)}")
    print(f"total_issues: {summary.get('total_issues', 0)}")
    if result.remediation is not None:
        print(f"payer_listings: {len(result.remediation.payer_listings)}")
        print(f"field_discrepancies: {len(result.remediation.discrepancies)}")
    print(f"outputs: {args.output_dir}")


if __name__ == "__main__":
    main()
