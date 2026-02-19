"""Feed fetching and quality scoring for the media RSS desktop app."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Event
from typing import Any, Callable

import feedparser
import requests

USER_AGENT = "czech-media-rss-app/0.1 (+https://github.com/brozkeff/czech-media-rss-app)"
REQUEST_TIMEOUT = 6
MAX_HEADLINES_PER_SOURCE = 10


@dataclass
class NewsItem:
    """Single normalized news headline item."""

    source_name: str
    title: str
    link: str
    published: datetime


@dataclass
class FeedCandidateResult:
    """Quality score and error details for one feed candidate URL."""

    url: str
    score: float
    error: str | None = None
    item_count: int = 0


@dataclass
class SourceNewsResult:
    """Resolved result for one source after candidate selection."""

    source_id: str
    source_name: str
    chosen_feed: str | None
    headlines: list[NewsItem]
    status: str
    status_level: str
    score: float


def _to_utc(value: datetime) -> datetime:
    """Convert datetime to UTC while preserving absolute time."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_entry_datetime(entry: Any) -> datetime | None:
    """Parse publication datetime from feed entry data."""
    parsed_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_struct:
        return datetime(*parsed_struct[:6], tzinfo=timezone.utc)

    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return None

    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None

    return _to_utc(parsed)


def _fetch_and_parse(url: str) -> tuple[Any | None, str | None]:
    """Download and parse one RSS feed URL."""
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        return None, f"request failed: {exc}"

    if response.status_code != 200:
        return None, f"http {response.status_code}"

    parsed = feedparser.parse(response.content)
    if parsed.bozo and not getattr(parsed, "entries", None):
        bozo_error = getattr(parsed, "bozo_exception", "invalid feed")
        return None, f"parse failed: {bozo_error}"
    return parsed, None


def _score_feed(parsed: Any) -> tuple[float, int]:
    """Score feed quality using completeness, freshness, and duplicates."""
    entries = list(getattr(parsed, "entries", []) or [])
    if not entries:
        return 0.0, 0

    top = entries[:20]
    now = datetime.now(timezone.utc)

    valid = 0
    dated_entries: list[datetime] = []
    seen_titles: set[str] = set()
    duplicates = 0

    for entry in top:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        dt = _parse_entry_datetime(entry)
        if title and link:
            valid += 1
        if dt:
            dated_entries.append(dt)
        tnorm = title.lower()
        if tnorm in seen_titles and tnorm:
            duplicates += 1
        seen_titles.add(tnorm)

    completeness = valid / len(top)
    dated_ratio = len(dated_entries) / len(top)

    if dated_entries:
        latest_age_hours = max(0.0, (now - max(dated_entries)).total_seconds() / 3600.0)
        freshness = max(0.0, 1.0 - min(latest_age_hours, 96.0) / 96.0)
    else:
        freshness = 0.0

    duplicate_penalty = duplicates / len(top)
    count_bonus = min(len(entries), 20) / 20.0

    score = (
        50.0 * completeness
        + 30.0 * freshness
        + 15.0 * dated_ratio
        + 8.0 * count_bonus
        - 10.0 * duplicate_penalty
    )
    return max(score, 0.0), len(entries)


def _news_from_entries(source_name: str, entries: list[Any]) -> list[NewsItem]:
    """Normalize feed entries into displayable headline items."""
    items: list[NewsItem] = []
    for entry in entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        published = _parse_entry_datetime(entry) or datetime.now(timezone.utc)
        items.append(
            NewsItem(
                source_name=source_name,
                title=title,
                link=link,
                published=published,
            )
        )
        if len(items) >= MAX_HEADLINES_PER_SOURCE:
            break
    return items


def resolve_best_feed(source: dict[str, Any]) -> SourceNewsResult:
    """Resolve the best feed candidate for one configured source."""
    source_id = source["id"]
    source_name = source["name"]
    candidates = source["candidates"]

    candidate_results: list[FeedCandidateResult] = []
    best_score = -1.0
    best_feed = None
    best_parsed = None

    for url in candidates:
        parsed, error = _fetch_and_parse(url)
        if error:
            candidate_results.append(FeedCandidateResult(url=url, score=0.0, error=error))
            continue

        score, item_count = _score_feed(parsed)
        candidate_results.append(FeedCandidateResult(url=url, score=score, item_count=item_count))
        if score > best_score:
            best_score = score
            best_feed = url
            best_parsed = parsed

    if best_parsed is None or best_feed is None:
        summary = "; ".join(f"{c.url} ({c.error})" for c in candidate_results if c.error) or "no candidates"
        return SourceNewsResult(
            source_id=source_id,
            source_name=source_name,
            chosen_feed=None,
            headlines=[],
            status=f"Unavailable: {summary}",
            status_level="unavailable",
            score=0.0,
        )

    headlines = _news_from_entries(source_name, list(best_parsed.entries))
    status = f"Reliable ({len(headlines)} headlines, score {best_score:.1f})"
    status_level = "reliable"
    if len(headlines) < 2 or best_score < 35:
        status = f"Partial ({len(headlines)} headlines, score {best_score:.1f})"
        status_level = "partial"

    return SourceNewsResult(
        source_id=source_id,
        source_name=source_name,
        chosen_feed=best_feed,
        headlines=headlines,
        status=status,
        status_level=status_level,
        score=best_score,
    )


def get_latest_news(
    sources: list[dict[str, Any]],
    progress_callback: Callable[[int, int, SourceNewsResult], None] | None = None,
    cancel_event: Event | None = None,
) -> tuple[list[SourceNewsResult], list[NewsItem]]:
    """Resolve feeds for selected sources and return merged news items.

    Args:
        sources: Source definitions to fetch.
        progress_callback: Optional callback invoked after each resolved source.
        cancel_event: Optional event that interrupts processing between sources.

    Returns:
        Tuple of per-source results and sorted merged headlines.
    """
    results: list[SourceNewsResult] = []
    total = len(sources)

    for index, source in enumerate(sources, start=1):
        if cancel_event and cancel_event.is_set():
            break
        result = resolve_best_feed(source)
        results.append(result)
        if progress_callback:
            progress_callback(index, total, result)

    all_items = [item for source_result in results for item in source_result.headlines]
    all_items.sort(key=lambda item: item.published, reverse=True)
    return results, all_items
