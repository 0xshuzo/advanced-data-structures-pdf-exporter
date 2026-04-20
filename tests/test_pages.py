from __future__ import annotations

import pytest

from pdf_exporter.config import get_course
from pdf_exporter.models import DeckEntry, UpstreamSnapshot, build_fingerprint
from pdf_exporter.pages import SiteBuildError, build_pages_site


def test_build_pages_site_copies_pdfs_and_renders_download_page(tmp_path) -> None:
    course = get_course("advanced-data-structures")
    snapshot = UpstreamSnapshot(
        course=course.key,
        upstream_repo=course.upstream_repo,
        upstream_branch="main",
        checked_at="2026-04-20T00:00:00+00:00",
        fingerprint=build_fingerprint(
            [
                DeckEntry(
                    slug="advanced-data-structures",
                    slide_url="https://curiouscoding.nl/teaching/advanced-data-structures/slides/",
                    output_filename="advanced-data-structures-overview.pdf",
                    source_sha="abc123def456",
                    title="Advanced Data Structures",
                    subtitle="Week 1",
                )
            ]
        ),
        decks=(
            DeckEntry(
                slug="advanced-data-structures",
                slide_url="https://curiouscoding.nl/teaching/advanced-data-structures/slides/",
                output_filename="advanced-data-structures-overview.pdf",
                source_sha="abc123def456",
                title="Advanced Data Structures",
                subtitle="Week 1",
            ),
        ),
    )
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "advanced-data-structures-overview.pdf").write_bytes(b"%PDF-1.4 test")
    output_dir = tmp_path / "site"

    build_pages_site(
        snapshot=snapshot,
        pdf_dir=pdf_dir,
        output_dir=output_dir,
        repo_url="https://github.com/example/repo",
    )

    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Advanced Data Structures PDF Exporter" in html
    assert "Week 1" in html
    assert 'href="pdfs/advanced-data-structures-overview.pdf"' in html
    assert 'href="https://github.com/example/repo"' in html
    assert (output_dir / ".nojekyll").exists()
    assert (output_dir / "pdfs" / "advanced-data-structures-overview.pdf").read_bytes() == (
        b"%PDF-1.4 test"
    )


def test_build_pages_site_requires_exported_pdf(tmp_path) -> None:
    course = get_course("advanced-data-structures")
    snapshot = UpstreamSnapshot(
        course=course.key,
        upstream_repo=course.upstream_repo,
        upstream_branch="main",
        checked_at="2026-04-20T00:00:00+00:00",
        fingerprint="advanced-data-structures:abc123",
        decks=(
            DeckEntry(
                slug="advanced-data-structures",
                slide_url="https://curiouscoding.nl/teaching/advanced-data-structures/slides/",
                output_filename="advanced-data-structures-overview.pdf",
                source_sha="abc123",
            ),
        ),
    )

    with pytest.raises(SiteBuildError, match="Missing exported PDF"):
        build_pages_site(snapshot=snapshot, pdf_dir=tmp_path / "pdfs", output_dir=tmp_path / "site")
