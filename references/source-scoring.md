# Source Scoring Rubric

Score each source on four dimensions (0–2.5 each). Maximum total: **10/10**.

Apply this rubric in Step 3 of the workflow: first pre-score on Recency + Domain Authority from the search snippet, then complete Engagement + Depth after WebFetch.

---

## Dimension 1: Recency (0–2.5)

How recent is the content relative to today's date?

| Score | Criteria |
|-------|----------|
| 2.5 | Published within the last 24 hours |
| 2.0 | Published within the last 7 days |
| 1.5 | Published within the last 30 days |
| 1.0 | Published within the last 6 months |
| 0.5 | Published within the last 2 years |
| 0.0 | No visible date, or older than 2 years |

---

## Dimension 2: Domain Authority (0–2.5)

Is the source a credible, recognized publisher?

| Score | Criteria |
|-------|----------|
| 2.5 | Tier-1 news or research: Reuters, AP, BBC, NYT, Washington Post, Nature, IEEE, arXiv |
| 2.0 | Recognized tech/industry press: TechCrunch, Wired, The Verge, Bloomberg, Financial Times, Ars Technica |
| 1.5 | Established org blogs, well-known Substack authors with clear bylines, reputable industry analysts |
| 1.0 | General blogs or mid-sized publications with no obvious affiliation signals |
| 0.5 | Anonymous content, low-traffic personal sites, content aggregators without editorial standards |
| 0.0 | Spam indicators, missing author, no publication name, known misinformation domains |

---

## Dimension 3: Engagement Signals (0–2.5)

Does the URL or page show evidence of reach and social proof?

| Score | Criteria |
|-------|----------|
| 2.5 | High engagement: 1K+ shares/reactions, 500+ comments, HN/Reddit front page |
| 2.0 | Moderate: 100–999 shares or comments, or Reddit/HN top 50 |
| 1.5 | Some: any visible share/comment count > 10 |
| 1.0 | No visible count, but source is indexed by major news aggregators |
| 0.5 | No engagement data, no aggregator signals |
| 0.0 | Self-published with no distribution signals |

**Twitter/X special rules:**
- Verified account (blue/gold check): +0.5 bonus (capped at 2.5)
- Thread length ≥ 5 posts: treat as Depth proxy (+0.5 to Depth, not here)
- Retweet/like counts visible in snippet: use as engagement signal

---

## Dimension 4: Content Depth (0–2.5)

Does the content add analytical or factual value beyond a headline?

| Score | Criteria |
|-------|----------|
| 2.5 | In-depth article (800+ words), includes data/charts, expert quotes, or primary sources cited |
| 2.0 | Solid article (400–800 words) with at least one quoted source or data point |
| 1.5 | Short but grounded summary (<400 words) with factual claims |
| 1.0 | Tweet-length articles, press releases, minimal context |
| 0.5 | Primarily opinion without supporting evidence |
| 0.0 | Clickbait title with thin/unrelated body, or mostly ads |

---

## Scoring Procedure

1. **Pre-score** (before fetching): score Recency and Domain Authority from the search snippet.
2. **Pre-filter**: drop any URL with Domain Authority ≤ 0.5.
3. **Fetch**: call WebFetch on the top 10 candidates by pre-score.
4. **Complete score**: add Engagement Signals and Content Depth from page content.
5. **Final total** = sum of all four dimensions.

---

## Thresholds

| Score | Label | Action in report |
|-------|-------|-----------------|
| 8.0–10.0 | High quality | Feature prominently in highlights |
| 6.0–7.5 | Good quality | Include in tables |
| 4.0–5.5 | Moderate | Include with a note |
| < 4.0 | Low quality | Flag with ⚠️ warning; do not feature in highlights |

---

## Special Cases

| Source type | Authority | Notes |
|-------------|-----------|-------|
| Paywalled content | Score normally | Set Depth = 1.0 (can't verify body). Add "paywalled" note. |
| arXiv / academic preprints | 2.0 | Recency from submission date. High Depth if methods are present. |
| Reddit threads | 1.5 | Engagement from upvote count. Depth from top-comment quality. |
| Hacker News | 1.5 | Engagement from points + comment count. Depth from discussion quality. |
| Twitter/X threads | Variable | Treat full thread as one source. Thread length ≥ 5 posts → Depth 2.0. |
| Company press releases | 1.0 | Biased by definition; note in Research Notes. |
