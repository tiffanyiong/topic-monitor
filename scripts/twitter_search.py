#!/usr/bin/env python3
"""
Twitter/X search for topic-monitor skill via TwitterAPI.io.

Usage:
    python3 twitter_search.py "openAI" [--max 10] [--type Top|Latest]

On first run with no API key configured, prompts the user to enter one
and saves it to ~/.claude/skills/topic-monitor/twitter_api_key.

Output: JSON array of tweet results to stdout.
"""

import sys
import json
import argparse
import os
import ssl
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError

def _make_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

_SSL_CONTEXT = _make_ssl_context()

CONFIG_DIR = Path(os.environ.get("TOPIC_MONITOR_CONFIG_DIR", Path.home() / ".claude" / "skills" / "topic-monitor")).expanduser()
KEY_FILE = CONFIG_DIR / "twitter_api_key"
API_BASE = "https://api.twitterapi.io"


def load_api_key() -> str | None:
    env_key = os.environ.get("TWITTER_API_KEY")
    if env_key:
        return env_key.strip()
    if KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()
        return key if key else None
    return None


def save_api_key(key: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(key.strip())
    KEY_FILE.chmod(0o600)


def prompt_for_key() -> str:
    print(
        "\n[topic-monitor] Twitter/X search requires a TwitterAPI.io API key.\n"
        "  • Sign up free at https://twitterapi.io (includes $1 free credit)\n"
        "  • After signing up, find your API key in the dashboard\n",
        file=sys.stderr
    )
    key = input("Paste your TwitterAPI.io API key (or press Enter to skip Twitter): ").strip()
    if key:
        save_api_key(key)
        print(f"[topic-monitor] API key saved to {KEY_FILE}", file=sys.stderr)
    return key


def get_api_key(interactive: bool = True) -> str | None:
    key = load_api_key()
    if key:
        return key
    if interactive:
        return prompt_for_key() or None
    return None


def search_tweets(keyword: str, max_results: int = 10, query_type: str = "Latest", api_key: str = None, days: int = 30) -> list[dict]:
    """Search tweets via TwitterAPI.io advanced search endpoint."""
    if not api_key:
        api_key = get_api_key(interactive=True)
    if not api_key:
        print("[topic-monitor] No Twitter API key — skipping Twitter search.", file=sys.stderr)
        return []

    import time
    since_time = int(time.time()) - (days * 86400)
    params = urlencode({
        "query": f"{keyword} lang:en",
        "queryType": query_type,
        "since_time": since_time,
    })
    url = f"{API_BASE}/twitter/tweet/advanced_search?{params}"
    req = Request(url, headers={"X-API-Key": api_key})

    try:
        with urlopen(req, timeout=15, context=_SSL_CONTEXT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 401:
            print(
                f"[topic-monitor] Twitter API key invalid (401). "
                f"Delete {KEY_FILE} and re-run to enter a new key.",
                file=sys.stderr
            )
        else:
            print(f"[topic-monitor] Twitter API error {e.code}: {body[:200]}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[topic-monitor] Twitter request failed: {e}", file=sys.stderr)
        return []

    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    tweets_raw = data.get("tweets", [])
    # Hard-filter by date before scoring
    filtered = []
    for t in tweets_raw:
        created = t.get("createdAt", "")
        if created:
            try:
                pub = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if pub >= cutoff:
                    filtered.append(t)
            except ValueError:
                filtered.append(t)  # keep if unparseable
        else:
            filtered.append(t)
    tweets_raw = filtered[:max_results]

    results = []
    for t in tweets_raw:
        author = t.get("author", {})
        followers = author.get("followers", 0)
        verified = author.get("isBlueVerified", False)
        like_count = t.get("likeCount", 0)
        retweet_count = t.get("retweetCount", 0)
        reply_count = t.get("replyCount", 0)
        view_count = t.get("viewCount", 0)
        total_engagement = like_count + retweet_count * 2 + reply_count

        scores = _score_tweet(t, total_engagement, verified, followers)

        results.append({
            "url": t.get("url", ""),
            "text": t.get("text", ""),
            "author": author.get("userName", ""),
            "author_name": author.get("name", ""),
            "followers": followers,
            "verified": verified,
            "like_count": like_count,
            "retweet_count": retweet_count,
            "reply_count": reply_count,
            "view_count": view_count,
            "created_at": t.get("createdAt", "")[:10],
            "scores": scores,
            "quality_flag": "⚠️" if scores["total"] < 4.0 else "",
        })

    results.sort(key=lambda x: x["scores"]["total"], reverse=True)
    return results


def _score_tweet(tweet: dict, total_engagement: int, verified: bool, followers: int) -> dict:
    """Score a tweet using the same 4-dimension rubric (max 10)."""
    from datetime import datetime, timezone

    # 1. Recency
    recency = 1.0
    created = tweet.get("createdAt", "")
    if created:
        try:
            pub = datetime.fromisoformat(created.replace("Z", "+00:00"))
            delta = (datetime.now(timezone.utc) - pub).days
            if delta <= 1:
                recency = 2.5
            elif delta <= 7:
                recency = 2.0
            elif delta <= 30:
                recency = 1.5
            elif delta <= 180:
                recency = 1.0
            else:
                recency = 0.5
        except ValueError:
            pass

    # 2. Authority — based on follower tier + verification
    if followers >= 1_000_000:
        authority = 2.5
    elif followers >= 100_000:
        authority = 2.0
    elif followers >= 10_000:
        authority = 1.5
    elif followers >= 1_000:
        authority = 1.0
    else:
        authority = 0.5
    if verified:
        authority = min(2.5, authority + 0.5)

    # 3. Engagement
    if total_engagement >= 1000:
        engagement = 2.5
    elif total_engagement >= 100:
        engagement = 2.0
    elif total_engagement >= 10:
        engagement = 1.5
    elif total_engagement > 0:
        engagement = 1.0
    else:
        engagement = 0.5

    # 4. Content Depth — tweet text length as proxy
    text = tweet.get("text", "")
    words = len(text.split())
    # Check if it's a thread (longer content) via quoteCount as signal
    is_thread = tweet.get("quoteCount", 0) > 5 or words > 50
    if is_thread and words > 50:
        depth = 2.0
    elif words > 30:
        depth = 1.5
    elif words > 10:
        depth = 1.0
    else:
        depth = 0.5

    total = recency + authority + engagement + depth
    return {
        "recency": recency,
        "authority": authority,
        "engagement": engagement,
        "depth": depth,
        "total": round(total, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Twitter search for topic-monitor")
    parser.add_argument("keyword", help="Search keyword")
    parser.add_argument("--max", type=int, default=10, help="Max results (default 10)")
    parser.add_argument("--type", dest="query_type", default="Latest",
                        choices=["Top", "Latest"], help="Query type (default Latest)")
    parser.add_argument("--key", default=None, help="API key (overrides saved key)")
    args = parser.parse_args()

    api_key = args.key or get_api_key(interactive=True)
    if not api_key:
        print(json.dumps([]))
        return

    results = search_tweets(args.keyword, args.max, args.query_type, api_key)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
