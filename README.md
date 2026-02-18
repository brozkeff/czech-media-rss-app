# Czech Media RSS (Tkinter demo)

Small desktop demo app for browsing recent headlines from major Czech media outlets via RSS.

Showcases capability of GPT-5.3 Codex + agent personas from <https://github.com/N4M3Z/forge-council> to quickly build functional app. App prepared by installing forge-council, enabling `/experimental` Multi-agents feature and Linux Bubblewrap sandbox, invoking `$Council "short prompt to make this app..."` $Council should "Convene a PAI-style council — 3-round debate where specialists challenge each other."

![Screenshot of running demo app.](screenshots/screenshot1.png)

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
