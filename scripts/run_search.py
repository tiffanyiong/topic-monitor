#!/usr/bin/env python3
"""
Unified entry point for topic-monitor search.
Runs web search and optionally Twitter search concurrently,
then outputs a combined JSON report that Claude synthesizes into a final note.

Usage:
    python3 run_search.py "openAI"
    python3 run_search.py "openAI" --twitter
    python3 run_search.py "openAI" --twitter --max 10
    python3 run_search.py "openAI" --twitter --twitter-key YOUR_KEY

Output:
    JSON object with keys:
      keyword        - the search term
      date           - today YYYY-MM-DD
      web_results    - list of scored article objects
      tweet_results  - list of scored tweet objects (empty if --twitter not set)
      errors         - list of any non-fatal errors
"""

import sys
import json
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

# Allow running from any directory by adding scripts/ to path
import os
sys.path.insert(0, os.path.dirname(__file__))

import search as web_search_module
import twitter_search as twitter_module


def run(keyword: str, include_twitter: bool, max_results: int, twitter_key: str | None, days: int = 30) -> dict:
    errors = []
    web_results = []
    tweet_results = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}

        # Always run web search
        futures[pool.submit(web_search_module.run_web_search, keyword, max_results, days)] = "web"

        # Twitter is opt-in — fetch Latest + Top concurrently and merge
        if include_twitter:
            api_key = twitter_key or twitter_module.get_api_key(interactive=True)
            if api_key:
                def _fetch_both_twitter(kw, ak, d):
                    import time as _time
                    lat = twitter_module.search_tweets(kw, 8, "Latest", ak, d)
                    _time.sleep(6)  # free tier: 1 req/5s
                    top = twitter_module.search_tweets(kw, 8, "Top", ak, d)
                    return lat, top
                futures[pool.submit(_fetch_both_twitter, keyword, api_key, days)] = "twitter_both"
            else:
                errors.append("Twitter search skipped: no API key provided.")

        latest_tweets, top_tweets = [], []
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
                if source == "web":
                    web_results = result
                elif source == "twitter_both":
                    latest_tweets, top_tweets = result
            except Exception as e:
                errors.append(f"{source} search failed: {e}")

        if include_twitter and (latest_tweets or top_tweets):
            # Dedupe by URL, prefer higher score
            seen = {}
            for t in latest_tweets + top_tweets:
                url = t.get("url", "")
                if url not in seen or t["scores"]["total"] > seen[url]["scores"]["total"]:
                    seen[url] = t
            latest_urls = {t["url"] for t in latest_tweets}
            merged_latest = sorted([t for t in seen.values() if t["url"] in latest_urls], key=lambda x: x["scores"]["total"], reverse=True)
            merged_top    = sorted([t for t in seen.values() if t["url"] not in latest_urls], key=lambda x: x["scores"]["total"], reverse=True)
            tweet_results = []
            for i in range(max(len(merged_latest), len(merged_top))):
                if i < len(merged_latest) and len(tweet_results) < max_results:
                    tweet_results.append(merged_latest[i])
                if i < len(merged_top) and len(tweet_results) < max_results:
                    tweet_results.append(merged_top[i])

    return {
        "keyword": keyword,
        "date": date.today().isoformat(),
        "web_results": web_results,
        "tweet_results": tweet_results,
        "errors": errors,
        "stats": {
            "web_count": len(web_results),
            "tweet_count": len(tweet_results),
            "top_web_score": web_results[0]["scores"]["total"] if web_results else 0,
            "top_tweet_score": tweet_results[0]["scores"]["total"] if tweet_results else 0,
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run topic-monitor search (web + optional Twitter)"
    )
    parser.add_argument("keyword", help="Keyword to search")
    parser.add_argument(
        "--twitter", action="store_true",
        help="Include Twitter/X results (requires TwitterAPI.io key)"
    )
    parser.add_argument(
        "--max", type=int, default=10,
        help="Max results per source (default 10)"
    )
    parser.add_argument(
        "--twitter-key", default=None,
        help="TwitterAPI.io API key (overrides saved key)"
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Search window in days (default 30 for manual runs)"
    )
    args = parser.parse_args()

    output = run(args.keyword, args.twitter, args.max, args.twitter_key, args.days)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
