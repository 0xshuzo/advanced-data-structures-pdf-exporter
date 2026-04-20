"""Org-file parsing and deck entry construction."""

from __future__ import annotations

import re
from collections.abc import Mapping

from pdf_exporter.config import CourseConfig
from pdf_exporter.export.naming import build_output_filename
from pdf_exporter.models import DeckEntry


def extract_org_header(text: str, key: str) -> str:
    pattern = re.compile(rf"(?im)^#\+{re.escape(key)}:\s*(.+)$")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def maybe_build_deck_entry(
    entry: Mapping[str, object], text: str, course: CourseConfig
) -> DeckEntry | None:
    path = str(entry.get("path", ""))
    sha = str(entry.get("sha", ""))
    title = extract_org_header(text, "title")
    subtitle = extract_org_header(text, "subtitle")
    export_path = extract_org_header(text, "reveal_export_file_name")
    export_match = course.export_path_pattern.match(export_path)
    if not export_match:
        return None

    if not course.matches_org_headers(title, subtitle):
        return None

    slug = export_match.group(1)
    slide_url = course.build_slide_url(slug)
    return DeckEntry(
        slug=slug,
        slide_url=slide_url,
        output_filename=build_output_filename(slide_url, course=course),
        source_sha=sha,
        title=title,
        subtitle=subtitle,
        source_path=path,
    )
