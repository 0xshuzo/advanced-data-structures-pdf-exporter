"""Course-specific configuration for upstream discovery and export naming."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class CourseConfig:
    """Configuration values that vary by course/site integration."""

    key: str
    display_name: str
    upstream_repo: str
    site_root: str
    state_path: Path
    filename_overrides: Mapping[str, str] = field(default_factory=dict)
    org_path_pattern: re.Pattern[str] = re.compile(r"^teaching/[^/]+/[^/]+\.org$")
    export_path_pattern: re.Pattern[str] = re.compile(
        r"^\.\./\.\./static/teaching/([^/]+)/slides/index\.html$"
    )
    priority_slugs: tuple[str, ...] = ()

    def build_slide_url(self, slug: str) -> str:
        return f"{self.site_root}/teaching/{slug}/slides/"

    def matches_org_headers(self, title: str, subtitle: str) -> bool:
        course_lower = self.display_name.lower()
        return title.strip().lower() == course_lower or course_lower in subtitle.lower()

    def sort_key(self, slug: str) -> tuple[int, int, str]:
        try:
            return (0, self.priority_slugs.index(slug), slug)
        except ValueError:
            return (1, len(self.priority_slugs), slug)


ADVANCED_DATA_STRUCTURES = CourseConfig(
    key="advanced-data-structures",
    display_name="Advanced Data Structures",
    upstream_repo="RagnarGrootKoerkamp/research",
    site_root="https://curiouscoding.nl",
    state_path=Path(".github/state/advanced-data-structures-upstream.json"),
    filename_overrides={
        "https://curiouscoding.nl/teaching/advanced-data-structures/slides/": (
            "advanced-data-structures-overview.pdf"
        ),
        "https://curiouscoding.nl/teaching/models-of-computation/slides/": (
            "advanced-data-structures-models-of-computation.pdf"
        ),
    },
    priority_slugs=("advanced-data-structures",),
)

COURSES: dict[str, CourseConfig] = {
    ADVANCED_DATA_STRUCTURES.key: ADVANCED_DATA_STRUCTURES,
}

DEFAULT_COURSE = ADVANCED_DATA_STRUCTURES.key


def get_course(key: str) -> CourseConfig:
    try:
        return COURSES[key]
    except KeyError as exc:
        available = ", ".join(sorted(COURSES))
        raise KeyError(f"Unknown course '{key}'. Available courses: {available}") from exc
