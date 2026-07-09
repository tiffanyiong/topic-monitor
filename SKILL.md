---
name: topic-monitor
description: >
  Searches the web, news sources, and optionally Twitter/X for trending articles, tweets, and discussions about a keyword, then scores each source for authenticity and quality, and delivers a curated report. Supports topic subscriptions with daily email digests and GitHub Actions cloud scheduling. Triggered by: /topic-monitor KEYWORD, /topic-monitor follow/unfollow/list/pause/resume, /topic-monitor set ..., /topic-monitor setup email/twitter/github-actions, /topic-monitor test.
---

# Topic Monitor

Research trending content about any keyword. Python scripts do all the heavy fetching outside Claude's context window — Claude only synthesizes and delivers the final report.

---

## First-Time Setup (new users)

**1. Install dependencies**
```bash
pip3 install google-genai certifi
```

**2. Copy config and fill in your values**
```bash
cp ~/.claude/skills/topic-monitor/config.example.md \
   ~/.claude/skills/topic-monitor/config.md
# Edit config.md: set your obsidian_vault path and email_recipients
```

**3. Set up Gmail for email delivery**
```
/topic-monitor setup email
```
You'll need a [Gmail App Password](https://myaccount.google.com/apppasswords) (not your regular password). The setup wizard will guide you.

**4. Set up Gemini for AI synthesis**

Save your [Gemini API key](https://aistudio.google.com/apikey) (free tier works):
```bash
echo "YOUR_GEMINI_API_KEY" > ~/.claude/skills/topic-monitor/gemini_api_key
chmod 600 ~/.claude/skills/topic-monitor/gemini_api_key
```

**5. (Optional) Set up Twitter/X**
```
/topic-monitor setup twitter
```
Requires a [TwitterAPI.io](https://twitterapi.io) key ($1 free credit included).

**6. Set up auto-scheduling on macOS**

First, decide what fixed local time you'd like to receive your digest. The default plist runs once per day at 8:00am.

Edit `com.tiffany.topic-monitor.plist`:
- Replace the Python path (find yours with `which python3`)
- Replace `/Users/YOUR_USERNAME` with your username
- Adjust the `StartCalendarInterval` hour if you do not want 8am

Then register it:
```bash
cp com.tiffany.topic-monitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.tiffany.topic-monitor.plist
```

The digest will run at the fixed local time when your Mac is awake. If the user needs delivery while their computer is off, use GitHub Actions cloud scheduling.

**6b. Optional: cloud scheduling with GitHub Actions**

Use this when the user wants the digest to run even if their computer is off. The workflow lives at `.github/workflows/daily.yml` and reads credentials from GitHub Secrets. To set it up, route to **GitHub Actions Setup Workflow**.

Required GitHub Secrets:
- `GEMINI_API_KEY`
- `GMAIL_SENDER`
- `GMAIL_APP_PASSWORD`
- `EMAIL_RECIPIENTS`

Optional GitHub Secret:
- `TWITTER_API_KEY`

Optional GitHub Variables:
- `SCHEDULE_TIME` (default `08:00`)
- `SCHEDULE_TIMEZONE` (default `America/Los_Angeles`)
- `SCHEDULED_WINDOW_HOURS` (default `24`)

**7. Add your first topic and test**
```
/topic-monitor follow openAI
/topic-monitor test run
/topic-monitor test email
```

> **Security note:** `config.md`, credential files (`gemini_api_key`, `gmail_app_password`, `gmail_sender`, `twitter_api_key`), and `logs/` are all gitignored. They live only on your local machine and are never committed.

---

## Sub-command Router

Read the user's invocation first. Route to the correct workflow below.

| Invocation | Workflow |
|---|---|
| `/topic-monitor KEYWORD` | → **Search Workflow** |
| `/topic-monitor follow KEYWORD` | → **Follow Workflow** |
| `/topic-monitor unfollow KEYWORD` | → **Unfollow Workflow** |
| `/topic-monitor pause KEYWORD` | → **Pause Workflow** |
| `/topic-monitor resume KEYWORD` | → **Resume Workflow** |
| `/topic-monitor list` | → **List Workflow** |
| `/topic-monitor set ...` | → **Settings Workflow** |
| `/topic-monitor setup email` | → **Email Setup Workflow** |
| `/topic-monitor setup twitter` | → **Twitter Setup Workflow** |
| `/topic-monitor setup github-actions` | → **GitHub Actions Setup Workflow** |
| `/topic-monitor test email` | → **Test Email Workflow** |
| `/topic-monitor test run` | → **Test Run Workflow** |

---

## Search Workflow

For `/topic-monitor KEYWORD` — one-off manual search.

### Step 1 — Check if keyword is a new followed topic

Check `~/.claude/skills/topic-monitor/subscriptions.md`. If this keyword is NOT already in the list, ask after delivering the report:
> "Want me to add **KEYWORD** to your daily digest? (`/topic-monitor follow KEYWORD`)"

### Step 2 — Ask: web only or include Twitter?

Ask once:
> "Should I include Twitter/X posts, or web articles and news only?"

- **Web only** → `run_search.py` without `--twitter`
- **Include Twitter** → check `~/.claude/skills/topic-monitor/twitter_api_key`
  - Exists → use `--twitter`
  - Missing → tell user to run `/topic-monitor setup twitter` first

### Step 3 — Run the search script

Read `config.md` for `manual_window_days` (default 30 if not set).

**Web only:**
```bash
python3 ~/.claude/skills/topic-monitor/scripts/run_search.py "KEYWORD" --max 10 --days DAYS
```

**With Twitter:**
```bash
python3 ~/.claude/skills/topic-monitor/scripts/run_search.py "KEYWORD" --twitter --max 10 --days DAYS
```

Parse the JSON. If `errors` is non-empty, report them but continue. If `stats.web_count` < 5, tell user and ask if they want a broader search.

### Step 4 — Detect delivery target

Read `~/.claude/skills/topic-monitor/config.md`:
- `default_delivery: obsidian` → write to Obsidian vault
- `default_delivery: email` → use Gmail (requires email setup)
- Not set → inline in chat, then offer to save local `.md`

### Step 5 — Synthesize the report

Read `references/output-format.md`. Build the report:

- **Executive Summary** — 3–5 sentences on what's happening now
- **Top Articles & News** — table of top 5 web results, highlights for top 3
- **Twitter / Social Buzz** — table of top 5 tweets (omit if no Twitter results)
- **What's Trending** — 2–3 bullet insight block
- **Source Quality Table** — all results with scores
- **Research Notes** — errors, caveats, follow-up suggestions

Flag any source with `quality_flag: "⚠️"`.

### Step 6 — Deliver

| Mode | Action |
|---|---|
| Obsidian | Write to `<vault>/<default_subfolder>/<KEYWORD>/YYYY-MM-DD.md` (create subfolder per topic; sanitize keyword for folder name: replace `/ \ : * ? " < > \|` with `-`) |
| Local file | Write to `~/Desktop/topic-monitor/<KEYWORD>/YYYY-MM-DD.md` |
| Inline | Print full report in chat; offer to save `.md` |

Confirm with exact path.

---

## Follow Workflow

For `/topic-monitor follow KEYWORD`:

1. Read `~/.claude/skills/topic-monitor/subscriptions.md`
2. Check if keyword already exists (case-insensitive)
   - If yes: tell user it's already followed, show its current settings
   - If no: append a new entry:
     ```yaml
     - keyword: KEYWORD
       enabled: true
       days: 1
       twitter: false
     ```
3. Confirm: "Added **KEYWORD** to your daily digest. It will appear in tomorrow's 8am email."
4. Ask: "Want Twitter included for this topic? (`/topic-monitor set twitter KEYWORD on`)"

---

## Unfollow Workflow

For `/topic-monitor unfollow KEYWORD`:

1. Read `subscriptions.md`, find the matching entry (case-insensitive)
2. Remove the entire block for that keyword
3. Write the file back
4. Confirm: "Removed **KEYWORD** from your daily digest."

---

## Pause / Resume Workflow

For `/topic-monitor pause KEYWORD`:
- Find entry, set `enabled: false`, write file
- Confirm: "**KEYWORD** paused. It won't appear in the daily digest until you resume it."

For `/topic-monitor resume KEYWORD`:
- Find entry, set `enabled: true`, write file
- Confirm: "**KEYWORD** resumed. It will appear in tomorrow's digest."

---

## List Workflow

For `/topic-monitor list`:

1. Read `subscriptions.md` and `config.md`
2. Display topics table + recipients:

```
Your followed topics:

  #  Keyword              Status      Window  Twitter
  1  openAI               ✅ active    1d      off
  2  xai                  ✅ active    1d      off
  3  bay area start up    ⏸ paused    1d      off
  4  adobe                ✅ active    1d      off

Recipients (all topics):
  1  tiffanyiong924@gmail.com
  2  roryzhang95@gmail.com

Digest runs: local launchd at fixed time, or GitHub Actions cloud schedule
```

3. Offer quick actions:
   - "Pause a topic: `/topic-monitor pause KEYWORD`"
   - "Add a recipient: `/topic-monitor set recipients add email@example.com`"
   - "Remove a recipient: `/topic-monitor set recipients remove email@example.com`"

---

## Settings Workflow

For `/topic-monitor set KEY VALUE`:

Read `config.md`, update the relevant key, write it back. Map user-friendly commands to config keys:

| Command | Config key updated |
|---|---|
| `set schedule 8am PST` | `schedule_time`, `schedule_timezone` |
| `set window 24h` | `scheduled_window_hours` |
| `set email you@gmail.com` | `email_recipients` — replaces entire list with one address |
| `set recipients a@x.com, b@x.com` | `email_recipients` — replace entire list (global, all topics get same digest) |
| `set recipients add b@x.com` | Append one address to the global recipients list |
| `set recipients remove b@x.com` | Remove one address from the global recipients list |
| `set twitter on` | Update all subscriptions to `twitter: true` |
| `set twitter off` | Update all subscriptions to `twitter: false` |
| `set twitter KEYWORD on/off` | Update that one subscription's `twitter` field |

For `set recipients` commands:
- `set recipients a@x.com, b@x.com` → overwrite `email_recipients` with the full new list
- `set recipients add b@x.com` → read current `email_recipients`, append the new address, write back
- `set recipients remove b@x.com` → read current `email_recipients`, remove that address, write back
- After any change, confirm: "Digest will now be sent to: a@x.com, b@x.com"

After any local schedule change: remind the user to reload the launchd plist. For GitHub Actions, update repository Variables instead.
After any `twitter` change: remind user that `/topic-monitor setup twitter` is needed if no key is saved.

---

## Email Setup Workflow

For `/topic-monitor setup email`:

1. Check if already configured:
   ```bash
   python3 ~/.claude/skills/topic-monitor/scripts/send_email.py --check
   ```
   - Returns `configured:sender@gmail.com` → tell user it's already set up, offer to reconfigure
   - Returns `not_configured` → proceed

2. Guide the user step by step (read the instructions from `references/user-guide.md` under "First-Time Setup: Gmail Email Delivery")

3. Run interactive setup:
   ```bash
   python3 ~/.claude/skills/topic-monitor/scripts/send_email.py --setup
   ```
   This prompts for Gmail address + app password, tests the connection, and saves credentials.

4. On success: "Gmail is configured. Run `/topic-monitor test email` to send a test message."

---

## Twitter Setup Workflow

For `/topic-monitor setup twitter`:

1. Check if key exists: `~/.claude/skills/topic-monitor/twitter_api_key`
2. If missing, guide the user (read from `references/user-guide.md` under "First-Time Setup: Twitter/X Search")
3. Run:
   ```bash
   python3 ~/.claude/skills/topic-monitor/scripts/twitter_search.py --help
   ```
   The script will prompt for the key and save it.
4. Confirm and remind: "Twitter is configured. Enable it per topic with `/topic-monitor set twitter KEYWORD on`"

---

## GitHub Actions Setup Workflow

For `/topic-monitor setup github-actions`:

1. Read `references/github-actions.md` before guiding the user.
2. Explain the model briefly: the user's fork runs `.github/workflows/daily.yml` in GitHub's cloud; secrets stay in their repo; their local laptop does not need to be on.
3. Check whether the current skill/repo has `.github/workflows/daily.yml`. If it is missing, create it from the bundled template.
4. Check `subscriptions.md`; if there are no enabled topics, ask the user to add one with `/topic-monitor follow KEYWORD`.
5. Guide the user to set required GitHub Secrets: `GEMINI_API_KEY`, `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, `EMAIL_RECIPIENTS`. Mention optional `TWITTER_API_KEY`.
6. Guide the user to set optional GitHub Variables: `SCHEDULE_TIME`, `SCHEDULE_TIMEZONE`, `SCHEDULED_WINDOW_HOURS`.
7. If `gh` is available and authenticated, offer interactive commands like `gh secret set GEMINI_API_KEY`; do not ask the user to paste secrets into chat unless they explicitly choose that.
8. Tell the user to run the workflow manually once from the GitHub Actions tab, or use `gh workflow run "Topic Monitor Daily Digest"` when available.
9. On completion, remind them that Actions uses GitHub-hosted runners, so email can send even when their own machine is off.

---

## Test Email Workflow

For `/topic-monitor test email`:

```bash
python3 ~/.claude/skills/topic-monitor/scripts/send_email.py \
  --to EMAIL_FROM_CONFIG \
  --subject "Topic Monitor — Test Email" \
  --body "<h2>✅ Topic Monitor email is working!</h2><p>Your daily digest will arrive at your configured schedule.</p>" \
  --html
```

Report success or failure with the exact error message.

---

## Test Run Workflow

For `/topic-monitor test run`:

```bash
python3 ~/.claude/skills/topic-monitor/scripts/run_daily.py --dry-run
```

Print the output to the user so they can see what the daily digest will look like. Do not send email.

---

## Rules

- Never fabricate sources. All results come from script JSON — never invent URLs.
- Use `date` from the JSON for filenames and frontmatter.
- Never hard-code personal paths — read from `config.md` only.
- Do not call WebSearch or WebFetch — scripts handle all fetching.
- When editing `subscriptions.md`, preserve the comment header at the top of the file.
- Obsidian writes: one subfolder per topic keyword (sanitized), one dated file per run.
- Email is for scheduled/automated runs. Obsidian is for manual on-demand runs.
- Only followed topics (enabled: true in subscriptions.md) appear in the daily email digest.

## References

- `references/output-format.md` — note template
- `references/source-scoring.md` — scoring rubric
- `references/user-guide.md` — user-facing help and setup instructions
- `references/github-actions.md` — GitHub Actions cloud scheduling setup
- `scripts/run_search.py` — unified search entry point
- `scripts/run_daily.py` — daily batch runner
- `scripts/send_email.py` — Gmail SMTP sender
- `scripts/search.py` — web + news search engine
- `scripts/twitter_search.py` — TwitterAPI.io search
