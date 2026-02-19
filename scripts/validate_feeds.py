from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import feedparser
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from czech_media_rss_app.config import MEDIA_SOURCES

USER_AGENT = "czech-media-rss-app-feed-validator/0.2 (+https://github.com/brozkeff/czech-media-rss-app)"
TIMEOUT_SECONDS = 12


@dataclass
class FeedCheck:
    source_id: str
    source_name: str
    url: str
    ok: bool
    status_code: int | None
    final_url: str
    content_type: str
    bytes_count: int
    entries: int
    bozo: bool
    error: str


def check_url(source_id: str, source_name: str, url: str) -> FeedCheck:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return FeedCheck(
            source_id=source_id,
            source_name=source_name,
            url=url,
            ok=False,
            status_code=None,
            final_url="",
            content_type="",
            bytes_count=0,
            entries=0,
            bozo=False,
            error=f"request failed: {exc}",
        )

    parsed = None
    entries = 0
    bozo = False
    error = ""
    ok = False

    if response.status_code == 200:
        parsed = feedparser.parse(response.content)
        entries = len(list(getattr(parsed, "entries", []) or []))
        bozo = bool(getattr(parsed, "bozo", False))

        if bozo and entries == 0:
            error = f"parse failed: {getattr(parsed, 'bozo_exception', 'invalid feed')}"
        elif entries == 0:
            error = "no entries"
        else:
            ok = True
    else:
        error = f"http {response.status_code}"

    return FeedCheck(
        source_id=source_id,
        source_name=source_name,
        url=url,
        ok=ok,
        status_code=response.status_code,
        final_url=response.url,
        content_type=response.headers.get("content-type", ""),
        bytes_count=len(response.content),
        entries=entries,
        bozo=bozo,
        error=error,
    )


def run_checks() -> dict[str, object]:
    checks: list[FeedCheck] = []
    for source in MEDIA_SOURCES:
        for url in source["candidates"]:
            checks.append(check_url(source["id"], source["name"], url))

    total = len(checks)
    ok_count = sum(1 for check in checks if check.ok)
    failed = [asdict(check) for check in checks if not check.ok]

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "total_urls": total,
        "ok_urls": ok_count,
        "failed_urls": len(failed),
        "checks": [asdict(check) for check in checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate configured RSS feed URLs.")
    parser.add_argument(
        "--json-out",
        default="reports/feed_validation_latest.json",
        help="Path for the JSON validation report.",
    )
    args = parser.parse_args()

    report = run_checks()
    with open(args.json_out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(f"Validated {report['total_urls']} URLs: {report['ok_urls']} OK, {report['failed_urls']} failed")
    print(f"Report written to {args.json_out}")

    return 0 if report["failed_urls"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
