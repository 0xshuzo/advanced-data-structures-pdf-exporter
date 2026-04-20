"""Playwright-backed Reveal.js print-to-PDF export."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pdf_exporter.export.errors import PDFExportError


def build_print_pdf_url(slide_url: str) -> str:
    """Add the Reveal.js print-pdf query parameter to a deck URL."""
    parsed = urlparse(slide_url)
    existing = list(parse_qsl(parsed.query, keep_blank_values=True))
    if not any(key == "print-pdf" for key, _ in existing):
        existing.append(("print-pdf", ""))

    parts: list[str] = []
    for key, value in existing:
        if key == "print-pdf" and value == "":
            parts.append("print-pdf")
        else:
            parts.append(urlencode([(key, value)]))
    new_query = "&".join(parts) if parts else "print-pdf"

    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )


def _wait_for_reveal_ready(page, timeout_ms: int) -> None:
    page.wait_for_selector(".reveal, .slides", timeout=timeout_ms)
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 10_000))
    except Exception:
        pass
    page.wait_for_function(
        """
        () => {
            if (!window.Reveal) return true;
            if (typeof window.Reveal.isReady === 'function') return window.Reveal.isReady();
            return true;
        }
        """,
        timeout=timeout_ms,
    )
    page.wait_for_timeout(1200)


def _stabilize_layout_before_pdf(page, timeout_ms: int) -> None:
    page.emulate_media(media="print")
    try:
        page.wait_for_function(
            "() => !document.fonts || document.fonts.status === 'loaded'",
            timeout=timeout_ms,
        )
    except Exception:
        pass
    try:
        page.wait_for_function(
            """
            () => {
                const imgs = Array.from(document.images || []);
                return imgs.every(img => img.complete);
            }
            """,
            timeout=timeout_ms,
        )
    except Exception:
        pass
    page.evaluate(
        """
        () => {
            if (window.Reveal && typeof window.Reveal.layout === 'function') {
                window.Reveal.layout();
            }
            window.dispatchEvent(new Event('resize'));
        }
        """
    )
    page.wait_for_timeout(250)


def _get_pdf_dimensions(page) -> tuple[str, str]:
    dims = page.evaluate(
        """
        () => {
            const cfg = (window.Reveal && typeof window.Reveal.getConfig === 'function')
                ? window.Reveal.getConfig()
                : {};
            let w = Number(cfg.width) || 0;
            let h = Number(cfg.height) || 0;
            if (!w || !h) {
                const firstSlide = document.querySelector('.reveal .slides section');
                if (firstSlide) {
                    const rect = firstSlide.getBoundingClientRect();
                    if (!w) w = Math.round(rect.width);
                    if (!h) h = Math.round(rect.height);
                }
            }
            if (!w) w = 1920;
            if (!h) h = 1080;
            return { w, h };
        }
        """
    )
    width = max(640, int(dims.get("w", 1920)))
    height = max(360, int(dims.get("h", 1080)))
    return f"{width}px", f"{height}px"


def export_reveal_print_pdf(
    slide_url: str, outpath: Path, timeout: int, headless: bool = True
) -> None:
    """Export a Reveal.js deck via Chromium's print-to-PDF flow."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PDFExportError(
            "Playwright is required for reveal-print fallback but is not installed. "
            "Install dependencies and run: playwright install chromium"
        ) from exc

    print_url = build_print_pdf_url(slide_url)
    timeout_ms = timeout * 1000
    outpath.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            try:
                context = browser.new_context(viewport={"width": 1920, "height": 1080})
                page = context.new_page()
                response = page.goto(print_url, wait_until="domcontentloaded", timeout=timeout_ms)
                if response is not None and response.status >= 400:
                    raise PDFExportError(
                        f"Reveal print URL failed {print_url}: HTTP {response.status}"
                    )

                _wait_for_reveal_ready(page, timeout_ms=timeout_ms)
                _stabilize_layout_before_pdf(page, timeout_ms=timeout_ms)
                pdf_width, pdf_height = _get_pdf_dimensions(page)

                body_text = page.inner_text("body")[:2000].lower()
                if any(token in body_text for token in ("404", "not found", "error")):
                    if "reveal" not in body_text and "slides" not in body_text:
                        raise PDFExportError(
                            f"Loaded page at {print_url} appears to be an error page"
                        )

                page.pdf(
                    path=str(outpath),
                    print_background=True,
                    prefer_css_page_size=False,
                    width=pdf_width,
                    height=pdf_height,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
            finally:
                browser.close()
    except (PlaywrightError, PlaywrightTimeoutError) as exc:
        outpath.unlink(missing_ok=True)
        raise PDFExportError(f"Reveal print-to-PDF export failed for {slide_url}: {exc}") from exc
