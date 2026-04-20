"""Internal command runner for the Advanced Data Structures PDF Exporter."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from pdf_exporter.config import COURSES, DEFAULT_COURSE, get_course
from pdf_exporter.export import PDFExportError, build_decks_from_urls, format_export_result, process_deck
from pdf_exporter.http import DEFAULT_RETRIES, DEFAULT_TIMEOUT, build_browser_session
from pdf_exporter.pages import SiteBuildError, build_pages_site
from pdf_exporter.upstream.errors import UpstreamCheckError
from pdf_exporter.upstream.github import build_github_session
from pdf_exporter.upstream.service import build_snapshot
from pdf_exporter.upstream.state import (
    detect_changes,
    load_snapshot,
    write_github_output,
    write_snapshot,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Advanced Data Structures PDF Exporter maintenance commands."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export",
        help="Export slide decks from a manifest or explicit URLs.",
    )
    export_parser.add_argument("urls", nargs="*", help="One or more explicit slide deck URLs")
    export_parser.add_argument(
        "--course",
        choices=sorted(COURSES),
        help="Optional course config for naming overrides when exporting explicit URLs",
    )
    export_parser.add_argument(
        "--manifest-path",
        type=Path,
        help="Path to a manifest/snapshot JSON file produced by the upstream command",
    )
    export_parser.add_argument(
        "--outdir",
        type=Path,
        required=True,
        help="Output directory for generated PDF files",
    )
    export_parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Network/browser timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    export_parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Retry attempts for transient failures (default: {DEFAULT_RETRIES})",
    )
    export_parser.add_argument(
        "--headful",
        action="store_true",
        help="Launch Chromium in headed mode (default: headless)",
    )
    export_parser.set_defaults(handler=_run_export)

    upstream_parser = subparsers.add_parser(
        "upstream",
        help="Discover upstream decks, compare against state, and optionally write outputs.",
    )
    upstream_parser.add_argument(
        "--course",
        choices=sorted(COURSES),
        default=DEFAULT_COURSE,
        help=f"Course to discover (default: {DEFAULT_COURSE})",
    )
    upstream_parser.add_argument(
        "--state-path",
        type=Path,
        help="Path to the committed JSON state file (defaults to the course config path)",
    )
    upstream_parser.add_argument(
        "--write-state",
        action="store_true",
        help="Write the freshly fetched upstream snapshot to --state-path.",
    )
    upstream_parser.add_argument(
        "--manifest-path",
        type=Path,
        help="Write the discovered manifest/snapshot JSON to this path.",
    )
    upstream_parser.add_argument(
        "--github-output",
        action="store_true",
        help="Emit changed/fingerprint/reason values to $GITHUB_OUTPUT.",
    )
    upstream_parser.set_defaults(handler=_run_upstream)

    site_parser = subparsers.add_parser(
        "site",
        help="Build the static GitHub Pages site for the exported PDFs.",
    )
    site_parser.add_argument(
        "--manifest-path",
        type=Path,
        required=True,
        help="Path to a manifest/snapshot JSON file describing the PDFs to publish.",
    )
    site_parser.add_argument(
        "--pdf-dir",
        type=Path,
        required=True,
        help="Directory containing the exported PDF files referenced by the manifest.",
    )
    site_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where the static Pages site should be written.",
    )
    site_parser.add_argument(
        "--repo-url",
        help="Optional GitHub repository URL to link from the published page.",
    )
    site_parser.set_defaults(handler=_run_site)

    return parser


def _run_export(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    if args.retries < 0:
        parser.error("--retries must be >= 0")
    if args.manifest_path is not None and args.urls:
        parser.error("export accepts either explicit URLs or --manifest-path, not both")
    if args.manifest_path is None and not args.urls:
        parser.error("export requires at least one URL or --manifest-path")

    args.outdir.mkdir(parents=True, exist_ok=True)

    if args.manifest_path is not None:
        snapshot = load_snapshot(args.manifest_path)
        if snapshot is None:
            raise PDFExportError(f"Manifest file does not contain any decks: {args.manifest_path}")
        decks = list(snapshot.decks)
    else:
        course = get_course(args.course) if args.course else None
        decks = build_decks_from_urls(args.urls, course=course)

    failures: list[tuple[str, str]] = []
    session = build_browser_session(retries=args.retries)

    for deck in decks:
        print(f"Processing: {deck.slide_url}", flush=True)
        try:
            result = process_deck(
                session=session,
                deck=deck,
                outdir=args.outdir,
                timeout=args.timeout,
                headless=not args.headful,
            )
            print(format_export_result(result), flush=True)
        except Exception as exc:
            failures.append((deck.slide_url, str(exc)))
            print(f"ERROR | source={deck.slide_url} | {exc}", file=sys.stderr, flush=True)

    if failures:
        print("", file=sys.stderr, flush=True)
        print("One or more URLs failed:", file=sys.stderr, flush=True)
        for url, message in failures:
            print(f" - {url}: {message}", file=sys.stderr, flush=True)
        return 1

    return 0


def _run_upstream(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    course = get_course(args.course)
    state_path = args.state_path or course.state_path
    session = build_github_session(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))

    current = build_snapshot(session, course=course)
    previous = load_snapshot(state_path)
    diff = detect_changes(previous, current, course=course)

    if args.write_state:
        write_snapshot(state_path, current)
    if args.manifest_path is not None:
        write_snapshot(args.manifest_path, current)
    if args.github_output:
        write_github_output(
            changed=diff.changed,
            fingerprint=current.fingerprint,
            reason=diff.reason,
        )

    result = {
        "changed": diff.changed,
        "decks": {deck.slug: deck.to_dict() for deck in current.decks},
        "fingerprint": current.fingerprint,
        "reason": diff.reason,
        "state_path": str(state_path),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _run_site(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    snapshot = load_snapshot(args.manifest_path)
    if snapshot is None:
        raise SiteBuildError(f"Manifest file does not contain any decks: {args.manifest_path}")
    build_pages_site(
        snapshot=snapshot,
        pdf_dir=args.pdf_dir,
        output_dir=args.output_dir,
        repo_url=args.repo_url,
    )
    print(f"Built GitHub Pages site in {args.output_dir}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args, parser)
    except (PDFExportError, SiteBuildError, UpstreamCheckError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
