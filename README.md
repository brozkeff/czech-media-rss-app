# Czech Media RSS (Tkinter demo)

Small desktop demo app for browsing recent headlines from major Czech media outlets via RSS.

This repository is intentionally simple and public-demo friendly: it showcases a Codex + forge-council style workflow, deterministic feed selection, and basic UI behavior in Tkinter.

## What it does

- Shows a searchable multi-select list of Czech media sources.
- Includes a one-click preset (`Top Czech News`).
- Tries multiple feed candidates per source and selects the best one using deterministic scoring.
- Fetches in the background to keep the UI responsive.
- Displays latest headlines with source and UTC publish time.
- Opens article links in your default browser on double-click.

Default download limit is **10 headlines per source**.

## Requirements

- Python `>=3.10`
- `feedparser`, `requests`
- `tkinter` (OS package on many Linux distributions)

If `tkinter` is missing:

- Debian/Ubuntu: `sudo apt install python3-tk`
- Fedora: `sudo dnf install python3-tkinter`
- Arch: `sudo pacman -S tk`

## Quick start (uv)

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run czech-media-rss
```

Alternative install path:

```bash
uv venv
source .venv/bin/activate
uv sync
uv run python -m czech_media_rss_app.app
```

## Feed validation

All configured feed URLs were validated on **2026-02-18**.

Run a fresh check:

```bash
python3 scripts/validate_feeds.py --json-out reports/feed_validation_latest.json
```

Published validation artifacts:

- `reports/feed_validation_2026-02-18.md`
- `reports/feed_validation_2026-02-18.json`
- `reports/feed_validation_latest.json`

## Notes for demo users

- RSS feeds are third-party endpoints and can change or become unavailable.
- Feed quality and ordering are heuristic (best candidate per source, not a guarantee).
- This project is a demo prototype, not a production news aggregator.

## License

Licensed under **EUPL 1.2**. See `LICENSE`.
