"""Shared HTTP/session helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT = 45
DEFAULT_RETRIES = 3
DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
DEFAULT_BROWSER_HEADERS = {
    "User-Agent": DEFAULT_BROWSER_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.7",
}


def build_retry_session(
    retries: int,
    *,
    headers: Mapping[str, str] | None = None,
    allowed_methods: Sequence[str] = ("HEAD", "GET"),
) -> Session:
    retry_cfg = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=tuple(allowed_methods),
        backoff_factor=0.8,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_cfg)

    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if headers:
        session.headers.update(dict(headers))
    return session


def build_browser_session(retries: int = DEFAULT_RETRIES) -> Session:
    return build_retry_session(retries=retries, headers=DEFAULT_BROWSER_HEADERS)


def request_with_context(
    session: Session,
    *,
    method: str,
    url: str,
    timeout: int,
    error_type: type[Exception],
    failure_prefix: str = "HTTP",
    stream: bool = False,
) -> Response:
    try:
        return session.request(
            method=method,
            url=url,
            timeout=(min(10, timeout), timeout),
            allow_redirects=True,
            stream=stream,
        )
    except requests.RequestException as exc:
        raise error_type(f"{failure_prefix} {method} failed for {url}: {exc}") from exc
