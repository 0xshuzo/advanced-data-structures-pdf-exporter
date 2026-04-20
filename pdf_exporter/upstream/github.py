"""GitHub API access for upstream discovery."""

from __future__ import annotations

import base64

from requests import Session

from pdf_exporter.http import build_retry_session, request_with_context
from pdf_exporter.upstream.errors import UpstreamCheckError

API_VERSION = "2022-11-28"
USER_AGENT = "advanced-data-structures-pdf-exporter-upstream/3.0"


def build_github_session(token: str | None) -> Session:
    session = build_retry_session(
        retries=3,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": API_VERSION,
        },
        allowed_methods=("GET",),
    )
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    return session


def github_api_get_json(session: Session, url: str) -> object:
    response = request_with_context(
        session,
        method="GET",
        url=url,
        timeout=30,
        error_type=UpstreamCheckError,
        failure_prefix="GitHub API request",
    )
    if response.status_code >= 400:
        raise UpstreamCheckError(
            f"GitHub API request failed for {url}: HTTP {response.status_code} {response.text}"
        )
    return response.json()


def fetch_default_branch(session: Session, repo: str) -> str:
    repo_url = f"https://api.github.com/repos/{repo}"
    payload = github_api_get_json(session, repo_url)
    if not isinstance(payload, dict) or "default_branch" not in payload:
        raise UpstreamCheckError(f"Unexpected repository payload from {repo_url}")
    return str(payload["default_branch"])


def fetch_repo_tree(session: Session, repo: str, branch: str) -> list[dict[str, object]]:
    url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    payload = github_api_get_json(session, url)
    tree = payload.get("tree") if isinstance(payload, dict) else None
    if not isinstance(tree, list):
        raise UpstreamCheckError(f"Unexpected tree payload from {url}")
    return [entry for entry in tree if isinstance(entry, dict)]


def fetch_blob_text(session: Session, repo: str, sha: str) -> str:
    url = f"https://api.github.com/repos/{repo}/git/blobs/{sha}"
    payload = github_api_get_json(session, url)
    if not isinstance(payload, dict):
        raise UpstreamCheckError(f"Unexpected blob payload from {url}")

    content = payload.get("content")
    encoding = payload.get("encoding")
    if not isinstance(content, str) or encoding != "base64":
        raise UpstreamCheckError(f"Unexpected blob encoding for {url}")

    try:
        decoded = base64.b64decode(content, validate=False)
    except ValueError as exc:
        raise UpstreamCheckError(f"Failed to decode upstream blob {sha}") from exc
    return decoded.decode("utf-8", errors="replace")
