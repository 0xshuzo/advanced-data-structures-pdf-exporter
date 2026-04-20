"""Snapshot persistence, manifest I/O, and change detection."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pdf_exporter.config import CourseConfig
from pdf_exporter.models import SnapshotDiff, UpstreamSnapshot
from pdf_exporter.upstream.errors import UpstreamCheckError


def load_snapshot(path: Path) -> UpstreamSnapshot | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UpstreamCheckError(f"State file is not valid JSON: {path}") from exc

    if payload == {}:
        return None
    if not isinstance(payload, dict):
        raise UpstreamCheckError(f"State file is not a JSON object: {path}")

    try:
        return UpstreamSnapshot.from_dict(payload)
    except ValueError as exc:
        raise UpstreamCheckError(f"State file is not valid snapshot JSON: {path}") from exc


def write_snapshot(path: Path, snapshot: UpstreamSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def detect_changes(
    previous: UpstreamSnapshot | None,
    current: UpstreamSnapshot,
    course: CourseConfig,
) -> SnapshotDiff:
    if previous is None:
        return SnapshotDiff(changed=True, reason="bootstrap:no_previous_state")

    reasons: list[str] = []
    previous_decks = previous.by_slug()
    current_decks = current.by_slug()

    previous_slugs = set(previous_decks)
    current_slugs = set(current_decks)

    for slug in sorted(current_slugs - previous_slugs, key=course.sort_key):
        reasons.append(f"{slug}:added")
    for slug in sorted(previous_slugs - current_slugs, key=course.sort_key):
        reasons.append(f"{slug}:removed")
    for slug in sorted(previous_slugs & current_slugs, key=course.sort_key):
        previous_sha = previous_decks[slug].source_sha
        current_sha = current_decks[slug].source_sha
        if previous_sha != current_sha:
            reasons.append(f"{slug}:{previous_sha[:12]}->{current_sha[:12]}")

    if not reasons:
        return SnapshotDiff(changed=False, reason="no_change")
    return SnapshotDiff(changed=True, reason=";".join(reasons))


def write_github_output(*, changed: bool, fingerprint: str, reason: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        raise UpstreamCheckError("--github-output was passed but GITHUB_OUTPUT is unset")

    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"changed={'true' if changed else 'false'}\n")
        handle.write(f"fingerprint={fingerprint}\n")
        handle.write(f"reason={reason}\n")
