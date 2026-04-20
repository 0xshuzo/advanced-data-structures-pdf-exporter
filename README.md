# Advanced Data Structures PDF Exporter

Advanced Data Structures PDF Exporter downloads the course PDFs from
`curiouscoding.nl`, keeps them up to date with GitHub Actions, and publishes
them via GitHub Pages.

## Structure

- `requirements.txt`: runtime dependencies for the workflows
- `requirements-dev.txt`: optional local test dependencies
- `pdf_exporter/cli.py`: internal command runner used from the repository root
- `pdf_exporter/config.py`: course-specific configuration
- `pdf_exporter/models.py`: typed deck/snapshot/export result models
- `pdf_exporter/http.py`: shared HTTP/session helpers
- `pdf_exporter/export/`: direct-PDF discovery, Playwright printing, validation, orchestration
- `pdf_exporter/pages.py`: GitHub Pages site generation for downloadable PDFs
- `pdf_exporter/upstream/`: GitHub API access, org parsing, snapshot/state logic
- `tests/`: unit tests for naming, parsing, diffing, serialization, and export flow behavior
- `.github/state/advanced-data-structures-upstream.json`: committed upstream state
- `pdfs/`: exported PDFs tracked by the workflow

## Workflow-Only Usage

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
```

This repository is not intended to be packaged or published as an installable
CLI. The workflows run the internal module entrypoint directly from the checked
out repository with `python -m pdf_exporter ...`.

## Internal Commands

Export PDFs for explicit deck URLs:

```bash
python -m pdf_exporter export \
  --outdir ./pdfs \
  --timeout 45 \
  --retries 3 \
  https://curiouscoding.nl/teaching/advanced-data-structures/slides/
```

Discover the current course decks and write a manifest:

```bash
python -m pdf_exporter upstream \
  --course advanced-data-structures \
  --manifest-path /tmp/advanced-data-structures-manifest.json
```

Export from a manifest produced by the upstream command:

```bash
python -m pdf_exporter export \
  --manifest-path /tmp/advanced-data-structures-manifest.json \
  --outdir ./pdfs
```

Persist the discovered upstream state:

```bash
python -m pdf_exporter upstream \
  --course advanced-data-structures \
  --write-state
```

Build the static GitHub Pages site from the current state and exported PDFs:

```bash
python -m pdf_exporter site \
  --manifest-path .github/state/advanced-data-structures-upstream.json \
  --pdf-dir ./pdfs \
  --output-dir ./site
```

## Workflow model

The checker workflow polls the upstream source repository and triggers the
export workflow only when the discovered deck set or one of the source commits
changes. The export workflow discovers a richer manifest, exports PDFs from
that manifest, persists the committed upstream state, builds a static download
page, and deploys that page to GitHub Pages.

To publish the download page, enable GitHub Pages in the repository settings
and choose `GitHub Actions` as the source.
