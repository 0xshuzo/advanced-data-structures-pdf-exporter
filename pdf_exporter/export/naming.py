"""URL normalization and output naming."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from pdf_exporter.config import COURSES, CourseConfig


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path != "/" and not path.endswith("/"):
        path += "/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    slug_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if not slug_parts:
        base = parsed.netloc.replace(".", "-")
    elif slug_parts[-1] == "slides" and len(slug_parts) >= 2:
        base = slug_parts[-2]
    else:
        base = slug_parts[-1]
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", base).strip("-") or "deck"


def build_output_filename(url: str, course: CourseConfig | None = None) -> str:
    normalized = normalize_url(url)

    if course is not None and normalized in course.filename_overrides:
        return course.filename_overrides[normalized]

    for candidate_course in COURSES.values():
        if normalized in candidate_course.filename_overrides:
            return candidate_course.filename_overrides[normalized]

    slug = slug_from_url(url)
    return slug if slug.lower().endswith(".pdf") else f"{slug}.pdf"
