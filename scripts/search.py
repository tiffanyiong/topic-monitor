#!/usr/bin/env python3
"""
Web + news search for topic-monitor skill.
Uses Google News RSS (no API key required) for reliable, real-time results.
Fetches article metadata concurrently for scoring.

Usage:
    python3 search.py "openAI" [--max 10]

Output: JSON array of scored article results to stdout.
"""

import sys
import json
import argparse
import re
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


def _make_ssl_context() -> ssl.SSLContext:
    # macOS Python ships without CA certs; certifi fixes it
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

_SSL_CONTEXT = _make_ssl_context()

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

SPAM_DOMAINS = {
    "pinterest.com", "amazon.com", "ebay.com", "etsy.com",
    "yelp.com", "tripadvisor.com", "quora.com",
}

TIER1_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "nytimes.com", "washingtonpost.com", "theguardian.com",
    "nature.com", "science.org", "arxiv.org", "ieee.org",
    "economist.com", "ft.com", "bloomberg.com",
}

TIER2_DOMAINS = {
    "techcrunch.com", "theverge.com", "wired.com", "arstechnica.com",
    "venturebeat.com", "zdnet.com", "cnet.com", "engadget.com",
    "technologyreview.com", "hbr.org", "forbes.com", "businessinsider.com",
    "cnbc.com", "wsj.com", "time.com", "axios.com", "theatlantic.com",
    "fastcompany.com", "fortune.com", "nbcnews.com", "abcnews.go.com",
}


def _urlopen(req, timeout=10):
    return urlopen(req, timeout=timeout, context=_SSL_CONTEXT)


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def gnews_search(keyword: str, max_results: int = 20, days: int = 30) -> list[dict]:
    """Fetch Google News RSS for keyword. Returns list of article dicts."""
    from datetime import timedelta
    after_date = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
    # Google News supports `after:YYYY-MM-DD` as part of the query string
    query = f"{keyword} after:{after_date}"
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-US&gl=US&ceid=US:en"
    )
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _urlopen(req, timeout=12) as resp:
            xml = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[search] Google News RSS failed: {e}", file=sys.stderr)
        return []

    items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
    results = []
    for item in items[:max_results]:
        title_m = re.search(r"<title>(.*?)</title>", item)
        pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item)
        source_m = re.search(r"<source[^>]*>(.*?)</source>", item)
        source_url_m = re.search(r'<source url="([^"]+)"', item)
        glink_m = re.search(r"<link>(.*?)</link>", item)

        raw_title = _strip_tags(title_m.group(1)) if title_m else ""
        source_name = _strip_tags(source_m.group(1)) if source_m else ""
        source_url = source_url_m.group(1) if source_url_m else ""
        domain = urlparse(source_url).netloc.lower().removeprefix("www.") if source_url else ""
        glink = glink_m.group(1).strip() if glink_m else ""

        # Parse pub date
        pub_date = None
        if pub_m:
            try:
                pub_date = parsedate_to_datetime(pub_m.group(1)).date().isoformat()
            except Exception:
                pass

        # Strip source name appended by Google ("Title - Source Name")
        title = raw_title
        if source_name and title.endswith(f" - {source_name}"):
            title = title[: -(len(source_name) + 3)]

        if not domain or any(s in domain for s in SPAM_DOMAINS):
            continue

        results.append({
            "url": glink,          # Google redirect URL — still clickable
            "source_url": source_url,
            "title": title.strip(),
            "domain": domain,
            "source": source_name,
            "published_date": pub_date,
        })

    return results


def fetch_article_meta(item: dict, timeout: int = 7) -> dict:
    """Try to fetch article for word count. Skip gracefully on failure."""
    url = item.get("source_url", "")
    if not url or url == item.get("url", ""):
        return item
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with _urlopen(req, timeout=timeout) as resp:
            raw = resp.read(65536).decode("utf-8", errors="replace")
        text = _strip_tags(raw)
        item["word_count"] = len(text.split())
    except Exception:
        pass  # word_count stays unset; scoring uses 0
    return item


def score_source(item: dict) -> dict:
    """Apply 4-dimension scoring rubric (max 10.0)."""
    today = datetime.now(timezone.utc).date()

    # 1. Recency
    recency = 1.0  # default: unknown
    pub = item.get("published_date")
    if pub:
        try:
            delta = (today - datetime.fromisoformat(pub[:10]).date()).days
            if delta <= 1:   recency = 2.5
            elif delta <= 7:  recency = 2.0
            elif delta <= 30: recency = 1.5
            elif delta <= 180: recency = 1.0
            elif delta <= 730: recency = 0.5
            else:              recency = 0.0
        except ValueError:
            pass

    # 2. Domain Authority
    domain = item.get("domain", "")
    if any(d in domain for d in TIER1_DOMAINS):   authority = 2.5
    elif any(d in domain for d in TIER2_DOMAINS): authority = 2.0
    elif "github.com" in domain or "medium.com" in domain: authority = 1.5
    elif any(s in domain for s in SPAM_DOMAINS):  authority = 0.0
    else:                                          authority = 1.0

    # 3. Engagement (proxy: being in Google News top results = indexed)
    engagement = 1.5  # Google News inclusion is itself a curation signal

    # 4. Content Depth
    words = item.get("word_count", 0)
    if words >= 800:   depth = 2.5
    elif words >= 400: depth = 2.0
    elif words >= 100: depth = 1.5
    elif words > 0:    depth = 1.0
    else:              depth = 1.0  # couldn't fetch — assume moderate

    total = recency + authority + engagement + depth
    item["scores"] = {
        "recency": recency,
        "authority": authority,
        "engagement": engagement,
        "depth": depth,
        "total": round(total, 1),
    }
    item["quality_flag"] = "⚠️" if total < 4.0 else ""
    return item


def run_web_search(keyword: str, max_results: int = 10, days: int = 30) -> list[dict]:
    """Fetch from Google News RSS and return top scored results from last `days` days."""
    raw = gnews_search(keyword, max_results=max_results * 2, days=days)

    # Hard-filter: drop articles older than the cutoff before fetching
    today = datetime.now(timezone.utc).date()
    from datetime import timedelta
    cutoff = today - timedelta(days=days)
    raw = [
        item for item in raw
        if item.get("published_date") is None
        or datetime.fromisoformat(item["published_date"][:10]).date() >= cutoff
    ]

    # Concurrent fetch for word count
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_article_meta, item): item for item in raw}
        fetched = [f.result() for f in as_completed(futures)]

    scored = [score_source(item) for item in fetched]
    scored.sort(key=lambda x: x["scores"]["total"], reverse=True)
    return scored[:max_results]


def main():
    parser = argparse.ArgumentParser(description="Web/news search for topic-monitor")
    parser.add_argument("keyword", help="Search keyword")
    parser.add_argument("--max", type=int, default=10, help="Max results (default 10)")
    args = parser.parse_args()

    results = run_web_search(args.keyword, args.max)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
