"""Direct PDF discovery, probing, and download helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from requests import Session

from pdf_exporter.export.errors import PDFExportError
from pdf_exporter.export.naming import normalize_url
from pdf_exporter.http import request_with_context


def fetch_html(session: Session, url: str, timeout: int) -> str:
    """Fetch deck HTML with strict response checks."""
    response = request_with_context(
        session,
        method="GET",
        url=url,
        timeout=timeout,
        error_type=PDFExportError,
    )
    if response.status_code >= 400:
        raise PDFExportError(f"Failed to fetch slide HTML {url}: HTTP {response.status_code}")

    ctype = (response.headers.get("Content-Type") or "").lower()
    if "html" not in ctype and "xml" not in ctype and "text" not in ctype:
        snippet = response.text[:512].lower()
        if "<html" not in snippet and "<!doctype" not in snippet:
            raise PDFExportError(
                f"Unexpected content type for slide page {url}: {response.headers.get('Content-Type')}"
            )
    return response.text


def _iter_pdfish_strings(html: str) -> Iterable[str]:
    pattern = re.compile(r"([\w./:%?&=+\-~#]+\.pdf(?:[?#][^\"'\s<>)]*)?)", re.IGNORECASE)
    for match in pattern.finditer(html):
        yield match.group(1)


def _add_candidate(candidates: list[str], seen: set[str], candidate: str) -> None:
    if candidate and candidate not in seen:
        seen.add(candidate)
        candidates.append(candidate)


def find_direct_pdf_candidates(slide_url: str, html: str) -> list[str]:
    """Discover likely direct PDF URLs from HTML and conservative heuristics."""
    soup = BeautifulSoup(html, "html.parser")
    parsed = urlparse(slide_url)
    slide_root = f"{parsed.scheme}://{parsed.netloc}"
    normalized_slide_url = normalize_url(slide_url)

    candidates: list[str] = []
    seen: set[str] = set()

    def resolve(raw: str) -> str:
        return urljoin(slide_url, raw.strip())

    for tag_name, attr in (
        ("a", "href"),
        ("link", "href"),
        ("iframe", "src"),
        ("embed", "src"),
        ("object", "data"),
    ):
        for tag in soup.find_all(tag_name):
            raw = tag.get(attr)
            if not raw:
                continue
            raw_str = str(raw).strip()
            if ".pdf" in raw_str.lower() or raw_str.lower().endswith("/pdf"):
                _add_candidate(candidates, seen, resolve(raw_str))

    for tag in soup.find_all(True):
        for attr_name, raw in tag.attrs.items():
            if not attr_name.startswith("data-"):
                continue
            values = raw if isinstance(raw, list) else [raw]
            for value in values:
                text = str(value).strip()
                if ".pdf" in text.lower():
                    _add_candidate(candidates, seen, resolve(text))

    for snippet in _iter_pdfish_strings(html):
        _add_candidate(candidates, seen, resolve(snippet))

    parsed_slide = urlparse(normalized_slide_url)
    path = parsed_slide.path
    no_trailing = path[:-1] if path.endswith("/") and path != "/" else path

    path_candidates = [
        f"{path}.pdf" if not path.endswith(".pdf") else path,
        f"{no_trailing}.pdf" if no_trailing and not no_trailing.endswith(".pdf") else no_trailing,
        urljoin(path if path.endswith("/") else f"{path}/", "index.pdf"),
        urljoin(path if path.endswith("/") else f"{path}/", "slides.pdf"),
        urljoin(path if path.endswith("/") else f"{path}/", "deck.pdf"),
        urljoin(path if path.endswith("/") else f"{path}/", "lecture.pdf"),
        urljoin(path if path.endswith("/") else f"{path}/", "pdf"),
        urljoin(path if path.endswith("/") else f"{path}/", "pdf/index.pdf"),
        urljoin(path if path.endswith("/") else f"{path}/", "pdf/slides.pdf"),
    ]

    for rel in path_candidates:
        if rel:
            _add_candidate(candidates, seen, urljoin(slide_root, rel))

    return candidates


def _looks_like_pdf_bytes(blob: bytes) -> bool:
    return blob.startswith(b"%PDF")


def _deck_tokens(slide_url: str) -> set[str]:
    parsed = urlparse(normalize_url(slide_url))
    raw_parts = [part for part in parsed.path.strip("/").split("/") if part]
    tokens: set[str] = set()
    ignored = {"slides", "teaching", "lecture", "lectures", "overview"}
    for part in raw_parts:
        for token in re.split(r"[-_.]+", part.lower()):
            if len(token) >= 3 and token not in ignored:
                tokens.add(token)
    return tokens


def is_relevant_direct_pdf_candidate(slide_url: str, candidate_url: str) -> bool:
    slide = urlparse(normalize_url(slide_url))
    candidate = urlparse(candidate_url)

    if candidate.netloc and candidate.netloc != slide.netloc:
        return False

    slide_dir = slide.path if slide.path.endswith("/") else f"{slide.path}/"
    candidate_path = candidate.path.lower()
    if candidate_path.startswith(slide_dir.lower()):
        return True

    deck_tokens = _deck_tokens(slide_url)
    if not deck_tokens:
        return False

    candidate_tokens = set(re.split(r"[^a-z0-9]+", candidate_path))
    overlap = len(deck_tokens.intersection(candidate_tokens))
    return overlap >= max(2, len(deck_tokens) // 2)


def probe_pdf_url(session: Session, pdf_url: str, timeout: int) -> bool:
    """Verify a candidate URL is a real PDF by headers and magic bytes."""
    head_response = request_with_context(
        session,
        method="HEAD",
        url=pdf_url,
        timeout=timeout,
        error_type=PDFExportError,
        stream=False,
    )
    if head_response.status_code < 400:
        ctype = (head_response.headers.get("Content-Type") or "").lower()
        if "application/pdf" in ctype:
            return True

    get_response = request_with_context(
        session,
        method="GET",
        url=pdf_url,
        timeout=timeout,
        error_type=PDFExportError,
        stream=True,
    )
    try:
        if get_response.status_code >= 400:
            return False
        ctype = (get_response.headers.get("Content-Type") or "").lower()
        sample = get_response.raw.read(8, decode_content=True)
        return _looks_like_pdf_bytes(sample) or "application/pdf" in ctype
    finally:
        get_response.close()


def download_pdf(session: Session, pdf_url: str, outpath: Path, timeout: int) -> None:
    """Download a validated direct PDF URL to disk."""
    response = request_with_context(
        session,
        method="GET",
        url=pdf_url,
        timeout=timeout,
        error_type=PDFExportError,
        stream=True,
    )
    try:
        if response.status_code >= 400:
            raise PDFExportError(f"Failed to download PDF {pdf_url}: HTTP {response.status_code}")

        outpath.parent.mkdir(parents=True, exist_ok=True)
        with outpath.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    handle.write(chunk)
    except Exception:
        outpath.unlink(missing_ok=True)
        raise
    finally:
        response.close()
