# Topic Monitor: Output Format

## Obsidian / Local Markdown Note

**Path conventions:**
- Obsidian: `<vault>/<default_subfolder>/YYYY-MM-DD <keyword>.md`
- Local file: `~/Desktop/topic-monitor/YYYY-MM-DD <keyword>.md`
- Filename sanitization: replace ` / \ : * ? " < > | ` with `-`

---

### Full Note Template

```markdown
---
keyword: "<keyword>"
date: YYYY-MM-DD
sources_checked: <total URLs reviewed>
top_score: <highest score out of 10>
avg_score: <average score, 1 decimal>
tags:
  - topic-monitor
  - research
---

# Topic Monitor: <keyword>
> Research run: YYYY-MM-DD

## Executive Summary

<3–5 sentences: what is currently happening with this topic, dominant narrative,
notable new developments, and overall sentiment.>

---

## Top Articles & News

| # | Title | Source | Date | Score | URL |
|---|-------|--------|------|-------|-----|
| 1 | Article title | Reuters | YYYY-MM-DD | 9.0/10 | https://... |
| 2 | ... | ... | ... | ... | ... |

### Article Highlights

**[Article Title]** — [Source Domain]
- Key claim 1
- Key claim 2
- Why it matters: <one sentence>

*(Repeat for top 3–5 articles)*

---

## Twitter / Social Buzz

| # | Content preview | Platform | Engagement | Score | URL |
|---|----------------|----------|------------|-------|-----|
| 1 | "First 100 chars of post..." | X/Twitter | — | 7.0/10 | https://... |
| 2 | ... | Reddit | 1.2K upvotes | 7.5/10 | https://... |

### Notable Posts

> "[Quote or summary of post content]"
> — [@handle or username], [Platform], [Date if known]

*(Repeat for top 3–5 social posts)*

---

## What's Trending

<2–3 bullets identifying dominant themes, emerging sub-topics, or narrative shifts>

- **Theme 1**: ...
- **Theme 2**: ...
- **Emerging angle**: ...

---

## Source Quality Table

| # | URL (truncated) | Domain | Recency | Authority | Engagement | Depth | Total |
|---|----------------|--------|---------|-----------|------------|-------|-------|
| 1 | reuters.com/... | Reuters | 2.5 | 2.5 | 2.0 | 2.5 | **9.5/10** |
| 2 | ... | ... | ... | ... | ... | ... | ... |

*Scoring: each dimension 0–2.5, max 10. See source-scoring.md for rubric.*

---

## Research Notes

<Any caveats, paywalled sources skipped, sources that couldn't be fetched,
follow-up search suggestions, or limitations of this run.>
```

---

## Gmail Draft Format

**Subject line:**
```
Topic Monitor Report: <keyword> — YYYY-MM-DD
```

**Body:** Paste the full note content above as plain text or Markdown-compatible HTML.

**MCP call:**
```
mcp__claude_ai_Gmail__create_draft
  to: <user-provided email>
  subject: "Topic Monitor Report: <keyword> — YYYY-MM-DD"
  body: <full report content>
```

Ask the user for their email address if it is not known. Do not guess or use stored values without confirmation.
