#!/usr/bin/env python3
"""
Daily batch runner for topic-monitor.
Reads subscriptions.md, runs search for each enabled topic,
synthesizes a rich report via Claude Haiku, and sends it via Gmail SMTP.

Usage:
    python3 run_daily.py                    # run all enabled subscriptions
    python3 run_daily.py --dry-run          # print report without sending email
    python3 run_daily.py --topic "openAI"  # run a single topic only
"""

import sys
import json
import argparse
import re
import os
from datetime import date, datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

import search as web_search_module
import twitter_search as twitter_module
import send_email as email_module

CONFIG_DIR = Path.home() / ".claude" / "skills" / "topic-monitor"
SUBSCRIPTIONS_FILE = CONFIG_DIR / "subscriptions.md"
CONFIG_FILE = CONFIG_DIR / "config.md"
LAST_SENT_FILE = CONFIG_DIR / "last_sent_date"

# Don't fire if it's before this hour (prevents accidental midnight/early wake triggers)
EARLIEST_HOUR = 8


def parse_config() -> dict:
    config = {
        "email_recipient": None,
        "scheduled_window_hours": 24,
        "schedule_delivery": "email",
    }
    if not CONFIG_FILE.exists():
        return config
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            config[key.strip()] = value.strip().strip('"')
    config["scheduled_window_hours"] = int(config.get("scheduled_window_hours", 24))
    return config


def parse_subscriptions() -> list[dict]:
    if not SUBSCRIPTIONS_FILE.exists():
        return []
    text = SUBSCRIPTIONS_FILE.read_text()
    blocks = re.split(r'\n(?=- keyword:)', text)
    subscriptions = []
    for block in blocks:
        if "keyword:" not in block:
            continue
        sub = {"enabled": True, "days": 1, "twitter": False}
        for line in block.splitlines():
            line = line.strip().lstrip("- ")
            if ":" in line and not line.startswith("#"):
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                if key == "keyword":
                    sub["keyword"] = val
                elif key == "enabled":
                    sub["enabled"] = val.lower() == "true"
                elif key == "days":
                    try:
                        sub["days"] = int(val)
                    except ValueError:
                        pass
                elif key == "twitter":
                    sub["twitter"] = val.lower() == "true"
        if "keyword" in sub:
            subscriptions.append(sub)
    return subscriptions


def run_search_for_topic(sub: dict, window_hours: int) -> dict:
    keyword = sub["keyword"]
    days = max(1, round(window_hours / 24))
    include_twitter = sub.get("twitter", False)

    web_results = web_search_module.run_web_search(keyword, max_results=10, days=days)

    tweet_results = []
    if include_twitter:
        api_key = twitter_module.get_api_key(interactive=False)
        if api_key:
            # Fetch Latest and Top concurrently, then merge: dedupe by URL, keep best score
            from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _ac
            import time as _time
            latest = twitter_module.search_tweets(keyword, 8, "Latest", api_key, days)
            _time.sleep(10)  # free tier: 1 req per 5s, 10s buffer for safety
            top    = twitter_module.search_tweets(keyword, 8, "Top",    api_key, days)

            # Merge: dedupe by URL, prefer higher score when duplicate
            seen = {}
            for t in latest + top:
                url = t.get("url", "")
                if url not in seen or t["scores"]["total"] > seen[url]["scores"]["total"]:
                    seen[url] = t

            # Balance: up to 5 from Latest + up to 5 from Top (by original source)
            latest_urls = {t["url"] for t in latest}
            merged_latest = [t for t in seen.values() if t["url"] in latest_urls]
            merged_top    = [t for t in seen.values() if t["url"] not in latest_urls]

            merged_latest.sort(key=lambda x: x["scores"]["total"], reverse=True)
            merged_top.sort(key=lambda x: x["scores"]["total"], reverse=True)

            # Interleave: alternating Latest/Top up to 10 total
            tweet_results = []
            for i in range(max(len(merged_latest), len(merged_top))):
                if i < len(merged_latest) and len(tweet_results) < 10:
                    tweet_results.append(merged_latest[i])
                if i < len(merged_top) and len(tweet_results) < 10:
                    tweet_results.append(merged_top[i])

    return {
        "keyword": keyword,
        "web_results": web_results,
        "tweet_results": tweet_results,
        "window_hours": window_hours,
    }


GEMINI_KEY_FILE = CONFIG_DIR / "gemini_api_key"


def load_gemini_key() -> str | None:
    if GEMINI_KEY_FILE.exists():
        key = GEMINI_KEY_FILE.read_text().strip()
        return key if key else None
    return os.environ.get("GEMINI_API_KEY")


def synthesize_topic(result: dict, api_key: str) -> dict:
    """Call Gemini Flash to generate executive summary, article highlights, and trending themes."""
    from google import genai

    keyword = result["keyword"]
    web = result["web_results"]
    tweets = result["tweet_results"]

    articles_text = "\n".join(
        f"- [{item.get('scores', {}).get('total', 0)}/10] \"{item.get('title', '')}\" — {item.get('source', '')} ({item.get('published_date', '')})"
        for item in web[:10]
    )
    tweets_text = "\n".join(
        f"- @{t.get('author', '')} ({t.get('followers', 0)} followers): {t.get('text', '')[:150]}"
        for t in tweets[:5]
    ) if tweets else "No tweets."

    prompt = f"""You are a research analyst. Based on the following news articles and tweets about "{keyword}" from the last 24 hours, write a concise intelligence report.

ARTICLES:
{articles_text}

TWEETS:
{tweets_text}

Write the report in this exact structure (use plain text, no markdown):

EXECUTIVE_SUMMARY
[3-4 sentences summarising what is happening with {keyword} right now. Be specific and factual.]

ARTICLE_HIGHLIGHTS
[For each of the top 3 articles, write:
TITLE: <article title>
INSIGHT: <1-2 sentences on why this matters>]

TRENDING_THEMES
[2-3 bullet points identifying the dominant themes or patterns across all sources. Each bullet starts with a theme name followed by a colon.]"""

    client = genai.Client(api_key=api_key)
    models_fallback = [
        "gemini-3.1-flash-lite-preview",
        "gemini-2.5-flash-lite",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
    ]
    response = None
    for model in models_fallback:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            print(f"[synthesize] Using {model}", file=sys.stderr)
            break
        except Exception as e:
            print(f"[synthesize] {model} failed: {e.__class__.__name__} — trying next", file=sys.stderr)
    if response is None:
        raise RuntimeError("All Gemini models failed during synthesis")

    raw = response.text.strip()
    result["synthesis"] = parse_synthesis(raw)
    return result


def parse_synthesis(text: str) -> dict:
    """Parse the structured synthesis output into a dict."""
    synthesis = {"executive_summary": "", "article_highlights": [], "trending_themes": []}

    summary_match = re.search(r"EXECUTIVE_SUMMARY\s*\n(.*?)(?=ARTICLE_HIGHLIGHTS|$)", text, re.DOTALL)
    if summary_match:
        synthesis["executive_summary"] = summary_match.group(1).strip()

    highlights_match = re.search(r"ARTICLE_HIGHLIGHTS\s*\n(.*?)(?=TRENDING_THEMES|$)", text, re.DOTALL)
    if highlights_match:
        block = highlights_match.group(1).strip()
        # Parse TITLE/INSIGHT pairs
        pairs = re.findall(r"TITLE:\s*(.+?)\nINSIGHT:\s*(.+?)(?=\nTITLE:|\Z)", block, re.DOTALL)
        for title, insight in pairs:
            synthesis["article_highlights"].append({
                "title": title.strip(),
                "insight": insight.strip()
            })

    trending_match = re.search(r"TRENDING_THEMES\s*\n(.*?)$", text, re.DOTALL)
    if trending_match:
        block = trending_match.group(1).strip()
        for line in block.splitlines():
            line = line.strip().lstrip("-•* ")
            if line:
                synthesis["trending_themes"].append(line)

    return synthesis


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


TOPIC_COLORS = [
    "#4a90d9", "#e34f26", "#6b4fbb", "#10a37f",
    "#e67e22", "#c0392b", "#1abc9c", "#8e44ad",
]


def _score_badge(score: float, flag: str = "") -> str:
    color = "#22c55e" if score >= 8 else "#f59e0b" if score >= 6 else "#ef4444"
    text = f"{score}{' ' + flag if flag else ''}"
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700">{text}</span>'


def format_topic_html(result: dict, color: str = "#4a90d9") -> str:
    """Format one topic as a self-contained card with all content sections."""
    keyword = result["keyword"]
    web = result["web_results"]
    tweets = result["tweet_results"]
    window = result["window_hours"]
    synthesis = result.get("synthesis", {})

    parts = []

    # ── Card wrapper open + colored header ────────────────────────────────────
    parts.append(
        f'<div style="margin-bottom:28px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08)">'
        f'<div style="background:{color};padding:16px 22px">'
        f'<h2 style="margin:0;color:white;font-size:19px;font-weight:700">🔍 {_esc(keyword)}</h2>'
        f'<p style="margin:4px 0 0;color:rgba(255,255,255,0.75);font-size:12px">Last {window}h &nbsp;·&nbsp; {len(web)} articles &nbsp;·&nbsp; {len(tweets)} tweets</p>'
        f'</div>'
        f'<div style="padding:22px 24px">'
    )

    # ── Executive Summary ─────────────────────────────────────────────────────
    if synthesis.get("executive_summary"):
        parts.append(
            f'<div style="background:#f0f7ff;border-left:4px solid {color};padding:14px 16px;margin-bottom:20px;border-radius:0 8px 8px 0">'
            f'<p style="margin:0;font-size:14px;line-height:1.7;color:#2c3e50">{_esc(synthesis["executive_summary"])}</p>'
            f'</div>'
        )

    # ── Top Articles table ────────────────────────────────────────────────────
    if web:
        parts.append('<h3 style="color:#2c3e50;font-size:14px;font-weight:700;margin:0 0 8px;text-transform:uppercase;letter-spacing:.5px">📰 Top Articles</h3>')
        parts.append('<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">')
        parts.append(
            '<tr style="background:#f8f9fa">'
            '<th style="padding:8px 10px;text-align:left;font-size:11px;color:#999;font-weight:600;text-transform:uppercase">Title</th>'
            '<th style="padding:8px 10px;text-align:left;font-size:11px;color:#999;font-weight:600;text-transform:uppercase;white-space:nowrap">Source</th>'
            '<th style="padding:8px 10px;text-align:left;font-size:11px;color:#999;font-weight:600;text-transform:uppercase;white-space:nowrap">Date</th>'
            '<th style="padding:8px 10px;text-align:center;font-size:11px;color:#999;font-weight:600;text-transform:uppercase">Score</th>'
            '</tr>'
        )
        for i, item in enumerate(web[:5]):
            bg = "#ffffff" if i % 2 == 0 else "#fafafa"
            score = item.get("scores", {}).get("total", 0)
            flag = item.get("quality_flag", "")
            title = _esc(item.get("title", ""))
            url = item.get("url", "#")
            source = _esc(item.get("source", item.get("domain", "")))
            pub = item.get("published_date", "")
            parts.append(
                f'<tr style="background:{bg}">'
                f'<td style="padding:8px 10px;border-bottom:1px solid #f0f0f0"><a href="{url}" style="color:#2980b9;text-decoration:none;font-weight:500">{title}</a></td>'
                f'<td style="padding:8px 10px;border-bottom:1px solid #f0f0f0;color:#666;white-space:nowrap">{source}</td>'
                f'<td style="padding:8px 10px;border-bottom:1px solid #f0f0f0;color:#666;white-space:nowrap">{pub}</td>'
                f'<td style="padding:8px 10px;border-bottom:1px solid #f0f0f0;text-align:center">{_score_badge(score, flag)}</td>'
                f'</tr>'
            )
        parts.append('</table>')
    else:
        parts.append('<p style="color:#999;font-style:italic;font-size:13px;margin-bottom:20px">No articles found in this window.</p>')

    # ── Article Highlights ────────────────────────────────────────────────────
    highlights = synthesis.get("article_highlights", [])
    if highlights:
        # Build a lookup: partial title match → url from web results
        url_lookup = {}
        for item in web:
            url_lookup[item.get("title", "").lower()] = item.get("url", "#")

        def _find_url(title: str) -> str:
            tl = title.lower()
            if tl in url_lookup:
                return url_lookup[tl]
            for key, url in url_lookup.items():
                if tl[:40] in key or key[:40] in tl:
                    return url
            return "#"

        parts.append('<h3 style="color:#2c3e50;font-size:14px;font-weight:700;margin:0 0 10px;text-transform:uppercase;letter-spacing:.5px">💡 Article Highlights</h3>')
        for h in highlights:
            h_url = _find_url(h["title"])
            title_html = (
                f'<a href="{h_url}" style="color:#2c3e50;text-decoration:none;font-weight:700;font-size:13px">{_esc(h["title"])} ↗</a>'
                if h_url != "#" else
                f'<span style="font-weight:700;font-size:13px;color:#2c3e50">{_esc(h["title"])}</span>'
            )
            parts.append(
                f'<div style="margin-bottom:10px;padding:12px 14px;border:1px solid #e8e8e8;border-radius:8px;background:#fafafa">'
                f'<p style="margin:0 0 5px">{title_html}</p>'
                f'<p style="margin:0;font-size:13px;color:#555;line-height:1.6">{_esc(h["insight"])}</p>'
                f'</div>'
            )
        parts.append('<div style="margin-bottom:20px"></div>')

    # ── Trending Themes ───────────────────────────────────────────────────────
    themes = synthesis.get("trending_themes", [])
    if themes:
        parts.append('<h3 style="color:#2c3e50;font-size:14px;font-weight:700;margin:0 0 8px;text-transform:uppercase;letter-spacing:.5px">📈 What\'s Trending</h3>')
        parts.append('<ul style="margin:0 0 20px;padding-left:20px">')
        for theme in themes:
            parts.append(f'<li style="font-size:13px;color:#444;line-height:1.7;margin-bottom:5px">{_esc(theme)}</li>')
        parts.append('</ul>')

    # ── Top Tweets ────────────────────────────────────────────────────────────
    if tweets:
        parts.append('<h3 style="color:#2c3e50;font-size:14px;font-weight:700;margin:0 0 8px;text-transform:uppercase;letter-spacing:.5px">🐦 Top Tweets</h3>')
        parts.append('<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">')
        parts.append(
            '<tr style="background:#f8f9fa">'
            '<th style="padding:8px 10px;text-align:left;font-size:11px;color:#999;font-weight:600;text-transform:uppercase;white-space:nowrap">Author</th>'
            '<th style="padding:8px 10px;text-align:left;font-size:11px;color:#999;font-weight:600;text-transform:uppercase">Tweet</th>'
            '<th style="padding:8px 10px;text-align:center;font-size:11px;color:#999;font-weight:600;text-transform:uppercase">Score</th>'
            '</tr>'
        )
        for i, tweet in enumerate(tweets[:5]):
            bg = "#ffffff" if i % 2 == 0 else "#fafafa"
            score = tweet.get("scores", {}).get("total", 0)
            flag = tweet.get("quality_flag", "")
            author = _esc(f"@{tweet.get('author', '')}")
            text = _esc(tweet.get("text", "")[:120]) + ("…" if len(tweet.get("text", "")) > 120 else "")
            url = tweet.get("url", "#")
            parts.append(
                f'<tr style="background:{bg}">'
                f'<td style="padding:8px 10px;border-bottom:1px solid #f0f0f0;color:#1da1f2;font-weight:700;white-space:nowrap">{author}</td>'
                f'<td style="padding:8px 10px;border-bottom:1px solid #f0f0f0"><a href="{url}" style="color:#555;text-decoration:none">{text}</a></td>'
                f'<td style="padding:8px 10px;border-bottom:1px solid #f0f0f0;text-align:center">{_score_badge(score, flag)}</td>'
                f'</tr>'
            )
        parts.append('</table>')

    # ── Source Quality Table (collapsible) ────────────────────────────────────
    if web:
        parts.append('<details style="margin-top:4px">')
        parts.append('<summary style="cursor:pointer;font-size:12px;color:#999;user-select:none;margin-bottom:8px">▸ Source Quality Table (all results)</summary>')
        parts.append('<table style="width:100%;border-collapse:collapse;font-size:12px">')
        parts.append(
            '<tr style="background:#f8f9fa">'
            '<th style="padding:6px 8px;text-align:left;color:#999;font-weight:600;font-size:11px;text-transform:uppercase">Title</th>'
            '<th style="padding:6px 8px;color:#999;font-weight:600;font-size:11px;text-transform:uppercase">Source</th>'
            '<th style="padding:6px 8px;text-align:center;color:#999;font-weight:600;font-size:11px;text-transform:uppercase">Recency</th>'
            '<th style="padding:6px 8px;text-align:center;color:#999;font-weight:600;font-size:11px;text-transform:uppercase">Authority</th>'
            '<th style="padding:6px 8px;text-align:center;color:#999;font-weight:600;font-size:11px;text-transform:uppercase">Engage</th>'
            '<th style="padding:6px 8px;text-align:center;color:#999;font-weight:600;font-size:11px;text-transform:uppercase">Depth</th>'
            '<th style="padding:6px 8px;text-align:center;color:#999;font-weight:600;font-size:11px;text-transform:uppercase">Total</th>'
            '</tr>'
        )
        for i, item in enumerate(web):
            bg = "#ffffff" if i % 2 == 0 else "#fafafa"
            s = item.get("scores", {})
            flag = item.get("quality_flag", "")
            title = _esc(item.get("title", "")[:55]) + ("…" if len(item.get("title", "")) > 55 else "")
            source = _esc(item.get("source", item.get("domain", "")))
            total = s.get("total", 0)
            total_color = "#22c55e" if total >= 8 else "#f59e0b" if total >= 6 else "#ef4444"
            parts.append(
                f'<tr style="background:{bg}">'
                f'<td style="padding:6px 8px;border-bottom:1px solid #f5f5f5;color:#444">{title}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #f5f5f5;color:#666;white-space:nowrap">{source}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #f5f5f5;text-align:center;color:#555">{s.get("recency", "")}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #f5f5f5;text-align:center;color:#555">{s.get("authority", "")}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #f5f5f5;text-align:center;color:#555">{s.get("engagement", "")}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #f5f5f5;text-align:center;color:#555">{s.get("depth", "")}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #f5f5f5;text-align:center;font-weight:700;color:{total_color}">{total} {flag}</td>'
                f'</tr>'
            )
        parts.append('</table></details>')

    # ── Card wrapper close ────────────────────────────────────────────────────
    parts.append('</div></div>')
    return "\n".join(parts)


def build_email_html(results: list[dict], run_date: str) -> str:
    topic_count = len(results)
    total_articles = sum(len(r["web_results"]) for r in results)
    total_tweets = sum(len(r["tweet_results"]) for r in results)

    topic_cards = "\n".join(
        format_topic_html(r, TOPIC_COLORS[i % len(TOPIC_COLORS)])
        for i, r in enumerate(results)
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif">
<div style="max-width:680px;margin:0 auto;padding:24px 16px">

  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:12px;padding:24px 28px;margin-bottom:24px">
    <h1 style="margin:0 0 6px;color:#ffffff;font-size:22px;font-weight:700">📡 Topic Monitor Daily Digest</h1>
    <p style="margin:0;color:#9ca3af;font-size:14px">{run_date} &nbsp;·&nbsp; {topic_count} topics &nbsp;·&nbsp; {total_articles} articles &nbsp;·&nbsp; {total_tweets} tweets</p>
  </div>

  {topic_cards}

  <p style="text-align:center;color:#9ca3af;font-size:11px;margin-top:8px">
    Sent by Topic Monitor &nbsp;·&nbsp; Manage topics via <code>/topic-monitor list</code> in Claude Code
  </p>
</div>
</body></html>"""


def already_sent_today() -> bool:
    if not LAST_SENT_FILE.exists():
        return False
    return LAST_SENT_FILE.read_text().strip() == date.today().isoformat()


def mark_sent_today():
    LAST_SENT_FILE.write_text(date.today().isoformat())


def main():
    parser = argparse.ArgumentParser(description="Topic Monitor daily digest runner")
    parser.add_argument("--dry-run", action="store_true", help="Print report without sending email")
    parser.add_argument("--topic", default=None, help="Run a single topic only")
    parser.add_argument("--force", action="store_true", help="Skip date-gate check and run regardless")
    args = parser.parse_args()

    # Date-gate: only send once per day, and not before EARLIEST_HOUR
    if not args.dry_run and not args.force:
        current_hour = datetime.now().hour
        if current_hour < EARLIEST_HOUR:
            print(f"[run_daily] Too early ({current_hour}h < {EARLIEST_HOUR}h minimum). Skipping.", file=sys.stderr)
            sys.exit(0)
        if already_sent_today():
            print(f"[run_daily] Digest already sent today ({date.today().isoformat()}). Skipping.", file=sys.stderr)
            sys.exit(0)

    config = parse_config()
    subscriptions = parse_subscriptions()

    if not subscriptions:
        print("[run_daily] No subscriptions found. Add topics to subscriptions.md", file=sys.stderr)
        sys.exit(0)

    active = [s for s in subscriptions if s.get("enabled", True)]
    if args.topic:
        active = [s for s in active if s["keyword"].lower() == args.topic.lower()]
    if not active:
        print("[run_daily] No active subscriptions to run.", file=sys.stderr)
        sys.exit(0)

    window_hours = int(config.get("scheduled_window_hours", 24))
    run_date = date.today().isoformat()

    print(f"[run_daily] Running {len(active)} topic(s) with {window_hours}h window...", file=sys.stderr)

    # Fetch search results concurrently
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(run_search_for_topic, sub, window_hours): sub["keyword"] for sub in active}
        for future in as_completed(futures):
            keyword = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"[run_daily] ✓ {keyword}: {len(result['web_results'])} articles, {len(result['tweet_results'])} tweets", file=sys.stderr)
            except Exception as e:
                print(f"[run_daily] ✗ {keyword} search failed: {e}", file=sys.stderr)

    if not results:
        print("[run_daily] All searches failed. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Sort to match subscription order
    order = {s["keyword"]: i for i, s in enumerate(active)}
    results.sort(key=lambda r: order.get(r["keyword"], 99))

    # Synthesize with Gemini Flash
    gemini_key = load_gemini_key()
    if not gemini_key:
        print("[run_daily] No Gemini API key found — skipping synthesis, sending raw results.", file=sys.stderr)
        print("[run_daily] Save key to ~/.claude/skills/topic-monitor/gemini_api_key to enable synthesis.", file=sys.stderr)
    else:
        print(f"[run_daily] Synthesising {len(results)} topic(s) with Gemini Flash...", file=sys.stderr)
        for result in results:
            try:
                synthesize_topic(result, gemini_key)
                print(f"[run_daily] ✓ Synthesised: {result['keyword']}", file=sys.stderr)
            except Exception as e:
                print(f"[run_daily] ✗ Synthesis failed for {result['keyword']}: {e}", file=sys.stderr)

    html_body = build_email_html(results, run_date)
    topic_names = ", ".join(r["keyword"] for r in results)
    subject = f"📡 Topic Monitor — {run_date} ({', '.join(r['keyword'] for r in results)})"

    if args.dry_run:
        print(f"\nSubject: {subject}")
        for r in results:
            print(f"\n=== {r['keyword']} ===")
            s = r.get("synthesis", {})
            if s.get("executive_summary"):
                print(f"Summary: {s['executive_summary'][:200]}...")
            for item in r["web_results"][:3]:
                score = item.get("scores", {}).get("total", 0)
                print(f"  [{score}] {item.get('title','')} ({item.get('source','')})")
        print("\n[dry-run] Email not sent.")
        sys.exit(0)

    # Support comma-separated recipients list; fall back to single email_recipient
    recipients_raw = config.get("email_recipients") or config.get("email_recipient")
    if not recipients_raw:
        print("[run_daily] No email_recipients in config.md.", file=sys.stderr)
        sys.exit(1)
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    if not email_module.is_configured():
        print("[run_daily] Gmail not configured. Run: python3 send_email.py --setup", file=sys.stderr)
        sys.exit(1)

    any_sent = False
    for recipient in recipients:
        success = email_module.send_email(recipient, subject, html_body, html=True)
        if success:
            print(f"[run_daily] ✓ Digest sent to {recipient}", file=sys.stderr)
            any_sent = True
        else:
            print(f"[run_daily] ✗ Failed to send to {recipient}.", file=sys.stderr)

    if any_sent:
        mark_sent_today()
        print(f"[run_daily] Marked {date.today().isoformat()} as sent. Won't run again until tomorrow.", file=sys.stderr)


if __name__ == "__main__":
    main()
