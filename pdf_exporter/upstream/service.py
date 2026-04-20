"""High-level upstream discovery orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

from requests import Session

from pdf_exporter.config import CourseConfig
from pdf_exporter.models import DeckEntry, UpstreamSnapshot, build_fingerprint
from pdf_exporter.upstream.errors import UpstreamCheckError
from pdf_exporter.upstream.github import (
    fetch_blob_text,
    fetch_default_branch,
    fetch_repo_tree,
)
from pdf_exporter.upstream.org import maybe_build_deck_entry


def discover_course_decks(
    session: Session, course: CourseConfig, branch: str
) -> tuple[DeckEntry, ...]:
    tree = fetch_repo_tree(session, repo=course.upstream_repo, branch=branch)
    decks: dict[str, DeckEntry] = {}

    for entry in tree:
        path = entry.get("path")
        entry_type = entry.get("type")
        sha = entry.get("sha")
        if entry_type != "blob" or not isinstance(path, str) or not isinstance(sha, str):
            continue
        if not course.org_path_pattern.match(path):
            continue

        text = fetch_blob_text(session, repo=course.upstream_repo, sha=sha)
        deck = maybe_build_deck_entry(entry, text, course)
        if deck is None:
            continue
        if deck.slug in decks:
            raise UpstreamCheckError(
                f"Discovered duplicate slide slug '{deck.slug}' from upstream source"
            )
        decks[deck.slug] = deck

    if not decks:
        raise UpstreamCheckError(f"No {course.display_name} slide decks were discovered")

    ordered_slugs = sorted(decks, key=course.sort_key)
    return tuple(decks[slug] for slug in ordered_slugs)


def build_snapshot(session: Session, course: CourseConfig) -> UpstreamSnapshot:
    branch = fetch_default_branch(session, repo=course.upstream_repo)
    decks = discover_course_decks(session, course=course, branch=branch)
    return UpstreamSnapshot(
        course=course.key,
        upstream_repo=course.upstream_repo,
        upstream_branch=branch,
        checked_at=datetime.now(timezone.utc).isoformat(),
        fingerprint=build_fingerprint(decks),
        decks=decks,
    )
