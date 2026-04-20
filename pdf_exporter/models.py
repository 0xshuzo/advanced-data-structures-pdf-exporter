"""Typed models shared by export and upstream flows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


def _require_string(
    payload: Mapping[str, object], key: str, context: str, default: str | None = None
) -> str:
    value = payload.get(key, default)
    if value is None:
        raise ValueError(f"{context} is missing required field '{key}'")
    if not isinstance(value, str):
        raise ValueError(f"{context} field '{key}' must be a string")
    return value


def build_fingerprint(decks: Iterable["DeckEntry"]) -> str:
    return "|".join(f"{deck.slug}:{deck.source_sha}" for deck in decks)


@dataclass(frozen=True, slots=True)
class DeckEntry:
    """A single discovered/exportable slide deck."""

    slug: str
    slide_url: str
    output_filename: str
    source_sha: str
    title: str = ""
    subtitle: str = ""
    source_path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "output_filename": self.output_filename,
            "slide_url": self.slide_url,
            "slug": self.slug,
            "source_path": self.source_path,
            "source_sha": self.source_sha,
            "subtitle": self.subtitle,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DeckEntry":
        from pdf_exporter.export.naming import build_output_filename

        context = "deck entry"
        slug = _require_string(payload, "slug", context)
        slide_url = _require_string(payload, "slide_url", context)
        output_filename = payload.get("output_filename")
        if output_filename is None:
            output_filename = build_output_filename(slide_url)
        if not isinstance(output_filename, str):
            raise ValueError(f"{context} field 'output_filename' must be a string")
        source_sha = _require_string(payload, "source_sha", context, default="")
        title = _require_string(payload, "title", context, default="")
        subtitle = _require_string(payload, "subtitle", context, default="")
        source_path = _require_string(payload, "source_path", context, default="")
        return cls(
            slug=slug,
            slide_url=slide_url,
            output_filename=output_filename,
            source_sha=source_sha,
            title=title,
            subtitle=subtitle,
            source_path=source_path,
        )


@dataclass(frozen=True, slots=True)
class UpstreamSnapshot:
    """Serializable snapshot/manifest of the currently discovered deck set."""

    course: str
    upstream_repo: str
    upstream_branch: str
    checked_at: str
    fingerprint: str
    decks: tuple[DeckEntry, ...]

    def by_slug(self) -> dict[str, DeckEntry]:
        return {deck.slug: deck for deck in self.decks}

    def to_dict(self) -> dict[str, object]:
        return {
            "checked_at": self.checked_at,
            "course": self.course,
            "decks": {deck.slug: deck.to_dict() for deck in self.decks},
            "fingerprint": self.fingerprint,
            "upstream_branch": self.upstream_branch,
            "upstream_repo": self.upstream_repo,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "UpstreamSnapshot":
        context = "upstream snapshot"
        raw_decks = payload.get("decks")
        decks: list[DeckEntry] = []

        if isinstance(raw_decks, Mapping):
            for slug, value in raw_decks.items():
                if not isinstance(slug, str) or not isinstance(value, Mapping):
                    raise ValueError(f"{context} field 'decks' must contain object values")
                deck_payload = dict(value)
                deck_payload.setdefault("slug", slug)
                decks.append(DeckEntry.from_dict(deck_payload))
        elif isinstance(raw_decks, list):
            for value in raw_decks:
                if not isinstance(value, Mapping):
                    raise ValueError(f"{context} field 'decks' must contain objects")
                decks.append(DeckEntry.from_dict(value))
        else:
            raise ValueError(f"{context} field 'decks' must be an object or list")

        fingerprint = payload.get("fingerprint")
        if fingerprint is None:
            fingerprint = build_fingerprint(decks)
        if not isinstance(fingerprint, str):
            raise ValueError(f"{context} field 'fingerprint' must be a string")

        return cls(
            course=_require_string(payload, "course", context, default=""),
            upstream_repo=_require_string(payload, "upstream_repo", context),
            upstream_branch=_require_string(payload, "upstream_branch", context),
            checked_at=_require_string(payload, "checked_at", context),
            fingerprint=fingerprint,
            decks=tuple(decks),
        )


@dataclass(frozen=True, slots=True)
class SnapshotDiff:
    changed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ExportResult:
    deck: DeckEntry
    mode: str
    output_path: Path
    size_bytes: int
    validated: bool
