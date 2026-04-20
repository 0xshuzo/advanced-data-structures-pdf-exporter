from __future__ import annotations

import json

from pdf_exporter.config import get_course
from pdf_exporter.models import DeckEntry, UpstreamSnapshot, build_fingerprint
from pdf_exporter.upstream.org import extract_org_header, maybe_build_deck_entry
from pdf_exporter.upstream.state import detect_changes, load_snapshot, write_snapshot


def test_extract_org_header_and_build_deck_entry() -> None:
    course = get_course("advanced-data-structures")
    entry = {"path": "teaching/2025/overview.org", "sha": "abc123def456"}
    text = """
#+TITLE: Advanced Data Structures
#+SUBTITLE: Week 1
#+REVEAL_EXPORT_FILE_NAME: ../../static/teaching/advanced-data-structures/slides/index.html
    """.strip()

    assert extract_org_header(text, "title") == "Advanced Data Structures"

    deck = maybe_build_deck_entry(entry, text, course)

    assert deck is not None
    assert deck.slug == "advanced-data-structures"
    assert deck.slide_url == "https://curiouscoding.nl/teaching/advanced-data-structures/slides/"
    assert deck.output_filename == "advanced-data-structures-overview.pdf"
    assert deck.source_sha == "abc123def456"


def test_detect_changes_between_snapshots() -> None:
    course = get_course("advanced-data-structures")
    previous = UpstreamSnapshot(
        course=course.key,
        upstream_repo=course.upstream_repo,
        upstream_branch="main",
        checked_at="2026-04-20T00:00:00+00:00",
        fingerprint="unused",
        decks=(
            DeckEntry(
                slug="advanced-data-structures",
                slide_url="https://curiouscoding.nl/teaching/advanced-data-structures/slides/",
                output_filename="advanced-data-structures-overview.pdf",
                source_sha="aaaaaaaaaaaa1111",
            ),
        ),
    )
    current = UpstreamSnapshot(
        course=course.key,
        upstream_repo=course.upstream_repo,
        upstream_branch="main",
        checked_at="2026-04-20T06:00:00+00:00",
        fingerprint="unused",
        decks=(
            DeckEntry(
                slug="advanced-data-structures",
                slide_url="https://curiouscoding.nl/teaching/advanced-data-structures/slides/",
                output_filename="advanced-data-structures-overview.pdf",
                source_sha="bbbbbbbbbbbb2222",
            ),
            DeckEntry(
                slug="models-of-computation",
                slide_url="https://curiouscoding.nl/teaching/models-of-computation/slides/",
                output_filename="advanced-data-structures-models-of-computation.pdf",
                source_sha="cccccccccccc3333",
            ),
        ),
    )

    diff = detect_changes(previous, current, course)

    assert diff.changed is True
    assert diff.reason == (
        "models-of-computation:added;"
        "advanced-data-structures:aaaaaaaaaaaa->bbbbbbbbbbbb"
    )


def test_snapshot_serialization_round_trip_and_bootstrap_state(tmp_path) -> None:
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
                    source_sha="abc123",
                    title="Advanced Data Structures",
                    subtitle="Week 1",
                    source_path="teaching/2025/overview.org",
                )
            ]
        ),
        decks=(
            DeckEntry(
                slug="advanced-data-structures",
                slide_url="https://curiouscoding.nl/teaching/advanced-data-structures/slides/",
                output_filename="advanced-data-structures-overview.pdf",
                source_sha="abc123",
                title="Advanced Data Structures",
                subtitle="Week 1",
                source_path="teaching/2025/overview.org",
            ),
        ),
    )
    path = tmp_path / "snapshot.json"

    write_snapshot(path, snapshot)
    loaded = load_snapshot(path)

    assert loaded == snapshot
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["decks"]["advanced-data-structures"]["output_filename"] == (
        "advanced-data-structures-overview.pdf"
    )

    empty_path = tmp_path / "empty.json"
    empty_path.write_text("{}\n", encoding="utf-8")
    assert load_snapshot(empty_path) is None


def test_legacy_snapshot_without_output_filename_is_supported(tmp_path) -> None:
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(
        json.dumps(
            {
                "checked_at": "2026-04-20T00:00:00+00:00",
                "decks": {
                    "advanced-data-structures": {
                        "slide_url": "https://curiouscoding.nl/teaching/advanced-data-structures/slides/",
                        "slug": "advanced-data-structures",
                        "source_path": "teaching/2025/overview.org",
                        "source_sha": "abc123",
                        "subtitle": "Week 1",
                        "title": "Advanced Data Structures",
                    }
                },
                "fingerprint": "advanced-data-structures:abc123",
                "upstream_branch": "main",
                "upstream_repo": "RagnarGrootKoerkamp/research",
            }
        ),
        encoding="utf-8",
    )

    loaded = load_snapshot(legacy_path)

    assert loaded is not None
    assert loaded.decks[0].output_filename == "advanced-data-structures-overview.pdf"
