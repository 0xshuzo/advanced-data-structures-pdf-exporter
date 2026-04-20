"""Static GitHub Pages site generation for Advanced Data Structures PDF Exporter."""

from __future__ import annotations

import html
import shutil
from datetime import datetime
from pathlib import Path

from pdf_exporter.config import get_course
from pdf_exporter.models import DeckEntry, UpstreamSnapshot


class SiteBuildError(RuntimeError):
    """Raised when the static site cannot be generated from the current files."""


def _format_timestamp(checked_at: str) -> str:
    try:
        dt = datetime.fromisoformat(checked_at)
    except ValueError:
        return checked_at
    return dt.strftime("%B %d, %Y %H:%M UTC")


def _format_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(size_bytes)} B"


def _display_title(deck: DeckEntry) -> str:
    if deck.title:
        return deck.title
    return deck.slug.replace("-", " ").title()


def _display_subtitle(deck: DeckEntry) -> str:
    if deck.subtitle:
        return deck.subtitle
    if deck.slug == "advanced-data-structures":
        return "Course overview"
    return "Lecture deck"


def _resolve_course_name(snapshot: UpstreamSnapshot) -> str:
    try:
        return get_course(snapshot.course).display_name
    except KeyError:
        return snapshot.course.replace("-", " ").title() or "Slide Decks"


def _copy_pdf(deck: DeckEntry, pdf_dir: Path, published_pdf_dir: Path) -> tuple[str, str]:
    source_path = pdf_dir / deck.output_filename
    if not source_path.exists():
        raise SiteBuildError(f"Missing exported PDF for deck '{deck.slug}': {source_path}")

    published_path = published_pdf_dir / deck.output_filename
    published_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, published_path)
    return f"pdfs/{deck.output_filename}", _format_size(source_path.stat().st_size)


def _render_deck_card(deck: DeckEntry, pdf_href: str, size_label: str) -> str:
    title = html.escape(_display_title(deck))
    subtitle = html.escape(_display_subtitle(deck))
    slide_url = html.escape(deck.slide_url, quote=True)
    pdf_link = html.escape(pdf_href, quote=True)
    sha = html.escape(deck.source_sha[:12] if deck.source_sha else "unknown")

    return f"""
      <article class="deck-card">
        <p class="deck-kicker">{html.escape(deck.slug)}</p>
        <h2>{title}</h2>
        <p class="deck-subtitle">{subtitle}</p>
        <div class="deck-meta">
          <span>{html.escape(size_label)}</span>
          <span>Source {sha}</span>
        </div>
        <div class="deck-actions">
          <a class="button primary" href="{pdf_link}" download>Download PDF</a>
          <a class="button secondary" href="{slide_url}">Open Slides</a>
        </div>
      </article>
    """.strip()


def _render_index(snapshot: UpstreamSnapshot, cards_html: str, repo_url: str | None) -> str:
    course_name = html.escape(_resolve_course_name(snapshot))
    checked_at = html.escape(_format_timestamp(snapshot.checked_at))
    repo_link = ""
    if repo_url:
        escaped_repo_url = html.escape(repo_url, quote=True)
        repo_link = f'<a class="repo-link" href="{escaped_repo_url}">View Repository</a>'

    deck_count = len(snapshot.decks)
    branch = html.escape(snapshot.upstream_branch)
    fingerprint = html.escape(snapshot.fingerprint[:24] or "n/a")

    page_title = f"{course_name} PDF Exporter"

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(page_title)}</title>
    <style>
      :root {{
        --bg: #f5efe4;
        --bg-accent: #dbe9e2;
        --ink: #14221c;
        --muted: #53635a;
        --panel: rgba(255, 250, 242, 0.84);
        --panel-border: rgba(20, 34, 28, 0.12);
        --primary: #0f6b52;
        --primary-strong: #0b4e3c;
        --secondary: #e6ded0;
        --shadow: 0 22px 55px rgba(20, 34, 28, 0.14);
      }}

      * {{ box-sizing: border-box; }}

      body {{
        margin: 0;
        min-height: 100vh;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(227, 195, 120, 0.28), transparent 32%),
          radial-gradient(circle at top right, rgba(15, 107, 82, 0.14), transparent 24%),
          linear-gradient(180deg, var(--bg) 0%, #f9f7f2 48%, var(--bg-accent) 100%);
        font-family: "Avenir Next", "Trebuchet MS", sans-serif;
      }}

      a {{
        color: inherit;
        text-decoration: none;
      }}

      .shell {{
        width: min(1100px, calc(100% - 2rem));
        margin: 0 auto;
        padding: 2rem 0 4rem;
      }}

      .hero {{
        position: relative;
        overflow: hidden;
        margin-top: 1rem;
        padding: 2.4rem;
        border: 1px solid var(--panel-border);
        border-radius: 28px;
        background: linear-gradient(140deg, rgba(255, 251, 245, 0.92), rgba(238, 246, 241, 0.88));
        box-shadow: var(--shadow);
      }}

      .hero::after {{
        content: "";
        position: absolute;
        inset: auto -4rem -4rem auto;
        width: 220px;
        height: 220px;
        border-radius: 999px;
        background: radial-gradient(circle, rgba(15, 107, 82, 0.24), transparent 68%);
      }}

      .eyebrow {{
        margin: 0 0 0.8rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        font-size: 0.78rem;
        color: var(--primary);
      }}

      h1 {{
        margin: 0;
        max-width: 12ch;
        font-family: "Palatino Linotype", "Book Antiqua", Palatino, serif;
        font-size: clamp(2.4rem, 6vw, 4.6rem);
        line-height: 0.95;
      }}

      .hero-copy {{
        max-width: 52rem;
        margin: 1rem 0 1.6rem;
        font-size: 1.08rem;
        line-height: 1.65;
        color: var(--muted);
      }}

      .hero-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        align-items: center;
      }}

      .pill {{
        padding: 0.55rem 0.9rem;
        border-radius: 999px;
        border: 1px solid var(--panel-border);
        background: rgba(255, 255, 255, 0.62);
        font-size: 0.92rem;
      }}

      .repo-link {{
        margin-left: auto;
        padding: 0.8rem 1.15rem;
        border-radius: 999px;
        background: var(--primary);
        color: white;
        font-weight: 600;
      }}

      .deck-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 1rem;
        margin-top: 1.6rem;
      }}

      .deck-card {{
        display: flex;
        flex-direction: column;
        gap: 0.9rem;
        padding: 1.35rem;
        border-radius: 24px;
        border: 1px solid var(--panel-border);
        background: var(--panel);
        box-shadow: var(--shadow);
        backdrop-filter: blur(12px);
      }}

      .deck-kicker {{
        margin: 0;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        font-size: 0.72rem;
        color: var(--primary);
      }}

      .deck-card h2 {{
        margin: 0;
        font-family: "Palatino Linotype", "Book Antiqua", Palatino, serif;
        font-size: 1.7rem;
        line-height: 1.05;
      }}

      .deck-subtitle {{
        margin: 0;
        color: var(--muted);
        line-height: 1.55;
      }}

      .deck-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
        color: var(--muted);
        font-size: 0.9rem;
      }}

      .deck-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.7rem;
        margin-top: auto;
      }}

      .button {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.78rem 1rem;
        border-radius: 14px;
        font-weight: 600;
      }}

      .button.primary {{
        background: var(--primary);
        color: white;
      }}

      .button.primary:hover {{
        background: var(--primary-strong);
      }}

      .button.secondary {{
        background: var(--secondary);
      }}

      .footer {{
        margin-top: 1.6rem;
        color: var(--muted);
        font-size: 0.92rem;
      }}

      @media (max-width: 720px) {{
        .hero {{
          padding: 1.5rem;
        }}

        .repo-link {{
          margin-left: 0;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <p class="eyebrow">Advanced Data Structures PDF Exporter</p>
        <h1>{html.escape(page_title)}</h1>
        <p class="hero-copy">
          Download the latest exported lecture PDFs, or open the live slide decks directly.
          This page is rebuilt by GitHub Actions whenever upstream slide sources change.
        </p>
        <div class="hero-meta">
          <span class="pill">{deck_count} decks</span>
          <span class="pill">Updated {checked_at}</span>
          <span class="pill">Branch {branch}</span>
          <span class="pill">Fingerprint {fingerprint}</span>
          {repo_link}
        </div>
      </section>
      <section class="deck-grid">
        {cards_html}
      </section>
      <p class="footer">
        Source repository: {html.escape(snapshot.upstream_repo)}.
      </p>
    </main>
  </body>
</html>
"""


def build_pages_site(
    snapshot: UpstreamSnapshot,
    pdf_dir: Path,
    output_dir: Path,
    repo_url: str | None = None,
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)

    published_pdf_dir = output_dir / "pdfs"
    cards: list[str] = []
    for deck in snapshot.decks:
        pdf_href, size_label = _copy_pdf(deck, pdf_dir=pdf_dir, published_pdf_dir=published_pdf_dir)
        cards.append(_render_deck_card(deck, pdf_href=pdf_href, size_label=size_label))

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    (output_dir / "index.html").write_text(
        _render_index(snapshot, cards_html="\n".join(cards), repo_url=repo_url),
        encoding="utf-8",
    )
