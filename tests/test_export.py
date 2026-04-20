from __future__ import annotations

import pytest

from pdf_exporter.config import get_course
from pdf_exporter.export.direct import (
    find_direct_pdf_candidates,
    is_relevant_direct_pdf_candidate,
)
from pdf_exporter.export.naming import build_output_filename, normalize_url
from pdf_exporter.export.reveal import build_print_pdf_url
from pdf_exporter.export.service import process_deck
from pdf_exporter.models import DeckEntry


def test_normalize_url_and_output_filename_generation() -> None:
    course = get_course("advanced-data-structures")

    assert normalize_url("https://example.com/course/slides?x=1#frag") == (
        "https://example.com/course/slides/"
    )
    assert build_output_filename(
        "https://curiouscoding.nl/teaching/advanced-data-structures/slides",
        course=course,
    ) == "advanced-data-structures-overview.pdf"
    assert build_output_filename("https://example.com/course-name/slides/") == "course-name.pdf"


def test_build_print_pdf_url_preserves_existing_query_and_fragment() -> None:
    assert build_print_pdf_url("https://example.com/slides/?foo=bar#deck") == (
        "https://example.com/slides/?foo=bar&print-pdf#deck"
    )
    assert build_print_pdf_url("https://example.com/slides/?print-pdf") == (
        "https://example.com/slides/?print-pdf"
    )


def test_direct_pdf_candidate_extraction_and_filtering() -> None:
    slide_url = "https://curiouscoding.nl/teaching/advanced-data-structures/slides/"
    html = """
    <html>
      <body>
        <a href="slides.pdf">Slides</a>
        <div data-pdf="../advanced-data-structures-reference.pdf"></div>
        <script>const ref = "assets/advanced-data-structures-handout.pdf";</script>
        <a href="https://example.com/unrelated.pdf">External</a>
      </body>
    </html>
    """

    candidates = find_direct_pdf_candidates(slide_url, html)

    assert "https://curiouscoding.nl/teaching/advanced-data-structures/slides/slides.pdf" in candidates
    assert (
        "https://curiouscoding.nl/teaching/advanced-data-structures/advanced-data-structures-reference.pdf"
        in candidates
    )
    assert (
        "https://curiouscoding.nl/teaching/advanced-data-structures/slides/assets/advanced-data-structures-handout.pdf"
        in candidates
    )
    assert is_relevant_direct_pdf_candidate(
        slide_url,
        "https://curiouscoding.nl/teaching/advanced-data-structures/slides/slides.pdf",
    )
    assert not is_relevant_direct_pdf_candidate(
        slide_url,
        "https://example.com/unrelated.pdf",
    )


def test_process_deck_prefers_direct_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    deck = DeckEntry(
        slug="advanced-data-structures",
        slide_url="https://curiouscoding.nl/teaching/advanced-data-structures/slides/",
        output_filename="advanced-data-structures-overview.pdf",
        source_sha="abc123",
    )

    monkeypatch.setattr("pdf_exporter.export.service.fetch_html", lambda **_: "<html></html>")
    monkeypatch.setattr(
        "pdf_exporter.export.service.find_direct_pdf_candidates",
        lambda *_: ["https://curiouscoding.nl/teaching/advanced-data-structures/slides/slides.pdf"],
    )
    monkeypatch.setattr(
        "pdf_exporter.export.service.is_relevant_direct_pdf_candidate",
        lambda *_: True,
    )
    monkeypatch.setattr("pdf_exporter.export.service.probe_pdf_url", lambda **_: True)

    def fake_download_pdf(*, outpath, **_kwargs) -> None:
        outpath.write_bytes(b"%PDF-1.4 direct")

    monkeypatch.setattr("pdf_exporter.export.service.download_pdf", fake_download_pdf)
    monkeypatch.setattr(
        "pdf_exporter.export.service.export_reveal_print_pdf",
        lambda *_args, **_kwargs: pytest.fail("reveal export should not run"),
    )

    result = process_deck(
        session=object(),
        deck=deck,
        outdir=tmp_path,
        timeout=45,
        headless=True,
    )

    assert result.mode == "direct-pdf"
    assert result.output_path.name == "advanced-data-structures-overview.pdf"
    assert result.output_path.read_bytes().startswith(b"%PDF")


def test_process_deck_falls_back_to_reveal_print(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    deck = DeckEntry(
        slug="models-of-computation",
        slide_url="https://curiouscoding.nl/teaching/models-of-computation/slides/",
        output_filename="advanced-data-structures-models-of-computation.pdf",
        source_sha="def456",
    )

    monkeypatch.setattr("pdf_exporter.export.service.fetch_html", lambda **_: "<html></html>")
    monkeypatch.setattr(
        "pdf_exporter.export.service.find_direct_pdf_candidates",
        lambda *_: ["https://curiouscoding.nl/teaching/models-of-computation/slides/slides.pdf"],
    )
    monkeypatch.setattr(
        "pdf_exporter.export.service.is_relevant_direct_pdf_candidate",
        lambda *_: True,
    )
    monkeypatch.setattr("pdf_exporter.export.service.probe_pdf_url", lambda **_: False)
    monkeypatch.setattr(
        "pdf_exporter.export.service.download_pdf",
        lambda **_kwargs: pytest.fail("direct download should not run"),
    )

    def fake_reveal_export(slide_url, outpath, timeout, headless) -> None:
        assert slide_url == deck.slide_url
        assert timeout == 45
        assert headless is True
        outpath.write_bytes(b"%PDF-1.4 fallback")

    monkeypatch.setattr("pdf_exporter.export.service.export_reveal_print_pdf", fake_reveal_export)

    result = process_deck(
        session=object(),
        deck=deck,
        outdir=tmp_path,
        timeout=45,
        headless=True,
    )

    assert result.mode == "reveal-print"
    assert result.output_path.name == "advanced-data-structures-models-of-computation.pdf"
    assert result.output_path.read_bytes().startswith(b"%PDF")
