from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import requests

USER_AGENT = "czech-media-rss-demo/0.1 (+https://github.com)"
REQUEST_TIMEOUT = 6
MAX_HEADLINES_PER_SOURCE = 10


@dataclass
class NewsItem:
    source_name: str
    title: str
    link: str
    published: datetime


@dataclass
class FeedCandidateResult:
    url: str
    score: float
    error: str | None = None
    item_count: int = 0


@dataclass
class SourceNewsResult:
    source_id: str
    source_name: str
    chosen_feed: str | None
    headlines: list[NewsItem]
    status: str
    score: float


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_entry_datetime(entry: Any) -> datetime | None:
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
            score=0.0,
        )

    headlines = _news_from_entries(source_name, list(best_parsed.entries))
    status = f"Reliable ({len(headlines)} headlines, score {best_score:.1f})"
    if len(headlines) < 2 or best_score < 35:
        status = f"Partial ({len(headlines)} headlines, score {best_score:.1f})"

    return SourceNewsResult(
        source_id=source_id,
        source_name=source_name,
        chosen_feed=best_feed,
        headlines=headlines,
        status=status,
        score=best_score,
    )


def get_latest_news(sources: list[dict[str, Any]]) -> tuple[list[SourceNewsResult], list[NewsItem]]:
    results = [resolve_best_feed(source) for source in sources]
    all_items = [item for source_result in results for item in source_result.headlines]
    all_items.sort(key=lambda item: item.published, reverse=True)
    return results, all_items
