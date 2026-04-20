"""High-level export orchestration."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from requests import Session

from pdf_exporter.config import CourseConfig
from pdf_exporter.export.direct import (
    download_pdf,
    fetch_html,
    find_direct_pdf_candidates,
    is_relevant_direct_pdf_candidate,
    probe_pdf_url,
)
from pdf_exporter.export.naming import build_output_filename, slug_from_url
from pdf_exporter.export.reveal import export_reveal_print_pdf
from pdf_exporter.export.validation import validate_pdf
from pdf_exporter.models import DeckEntry, ExportResult


def build_deck_entry_from_url(url: str, course: CourseConfig | None = None) -> DeckEntry:
    return DeckEntry(
        slug=slug_from_url(url),
        slide_url=url,
        output_filename=build_output_filename(url, course=course),
        source_sha="",
    )


def build_decks_from_urls(
    urls: Iterable[str], course: CourseConfig | None = None
) -> list[DeckEntry]:
    return [build_deck_entry_from_url(url, course=course) for url in urls]


def process_deck(
    session: Session,
    deck: DeckEntry,
    outdir: Path,
    timeout: int,
    headless: bool,
) -> ExportResult:
    outpath = outdir / deck.output_filename

    html = fetch_html(session=session, url=deck.slide_url, timeout=timeout)
    candidates = find_direct_pdf_candidates(deck.slide_url, html)

    for candidate in candidates:
        if not is_relevant_direct_pdf_candidate(deck.slide_url, candidate):
            continue
        if probe_pdf_url(session=session, pdf_url=candidate, timeout=timeout):
            download_pdf(session=session, pdf_url=candidate, outpath=outpath, timeout=timeout)
            validate_pdf(outpath)
            return ExportResult(
                deck=deck,
                mode="direct-pdf",
                output_path=outpath,
                size_bytes=outpath.stat().st_size,
                validated=True,
            )

    export_reveal_print_pdf(deck.slide_url, outpath, timeout=timeout, headless=headless)
    validate_pdf(outpath)
    return ExportResult(
        deck=deck,
        mode="reveal-print",
        output_path=outpath,
        size_bytes=outpath.stat().st_size,
        validated=True,
    )


def format_export_result(result: ExportResult) -> str:
    return (
        "OK"
        f" | source={result.deck.slide_url}"
        f" | mode={result.mode}"
        f" | out={result.output_path}"
        f" | size={result.size_bytes}"
        f" | validated={result.validated}"
    )
