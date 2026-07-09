# Topic Monitor

Topic Monitor is a Claude/Codex skill that tracks fresh news and optional Twitter/X posts for followed topics, scores source quality, synthesizes a concise Gemini-powered intelligence report, and emails a polished HTML digest automatically from GitHub Actions.

By default, the cloud scheduler sends the digest every day at **8:00 AM** in the configured timezone. Your laptop does not need to be awake.

![delivery](https://img.shields.io/badge/delivery-Gmail%20HTML%20digest-blue) ![ai](https://img.shields.io/badge/AI-Gemini%20Flash-orange) ![scheduler](https://img.shields.io/badge/scheduler-GitHub%20Actions-black)

---

## What It Does

- Searches Google News RSS for followed keywords; no web-search API key required.
- Optionally searches Twitter/X via TwitterAPI.io for topics with `twitter: true`.
- Scores every source for recency, authority, engagement, and depth.
- Uses Gemini to synthesize executive summaries, article highlights, and trending themes.
- Sends one HTML email digest covering all active topics.
- Runs in GitHub Actions, so scheduled delivery works even when your computer is off.

## Default Schedule

The included workflow runs hourly in UTC, but `scripts/run_daily.py --respect-schedule` only sends during the configured local hour.

Default values:

```text
SCHEDULE_TIME=08:00
SCHEDULE_TIMEZONE=America/Los_Angeles
SCHEDULED_WINDOW_HOURS=24
```

So out of the box, the digest is intended to send every morning at **8:00 AM Pacific time**. Change the repository Variables if you want a different local time or timezone.

## Delivery Modes

| Trigger | Destination | Format |
|---|---|---|
| GitHub Actions schedule | Gmail inbox | HTML digest for all active topics |
| GitHub Actions manual run | Gmail inbox | Immediate test digest |
| Manual `/topic-monitor KEYWORD` | Chat, local file, or Obsidian if configured | One-off research note |

---

## Quick Setup For Your Own Fork

### 1. Fork Or Clone This Repo

Fork `tiffanyiong/topic-monitor` into your own GitHub account, or clone it into your own repository. GitHub Actions and Secrets must live in the repository that will run your digest.

If you also want the skill available to your local agent, clone it into your skills directory:

```bash
git clone https://github.com/YOUR_USERNAME/topic-monitor \
  ~/.claude/skills/topic-monitor
```

### 2. Install Local Dependencies For Manual Testing

```bash
pip3 install google-genai certifi
```

GitHub Actions installs these automatically in the cloud.

### 3. Add Or Edit Topics

Edit `subscriptions.md` in your repo. Each enabled topic appears in the daily digest.

```yaml
- keyword: openAI
  enabled: true
  days: 1
  twitter: false
```

Set `twitter: true` only after adding the optional `TWITTER_API_KEY` secret.

### 4. Add Required GitHub Secrets

In your fork, go to **Settings -> Secrets and variables -> Actions -> New repository secret** and add:

| Secret | What to enter |
|---|---|
| `GEMINI_API_KEY` | Gemini API key from https://aistudio.google.com/apikey |
| `GMAIL_SENDER` | Gmail address that sends the digest |
| `GMAIL_APP_PASSWORD` | Gmail App Password, not your normal Gmail password |
| `EMAIL_RECIPIENTS` | Comma-separated recipient list, e.g. `you@gmail.com,friend@gmail.com` |

Optional:

| Secret | What to enter |
|---|---|
| `TWITTER_API_KEY` | TwitterAPI.io key for topics with `twitter: true` |

Never commit these values to the repo. They belong only in GitHub Secrets.

### 5. Set Optional GitHub Variables

In **Settings -> Secrets and variables -> Actions -> Variables**, set these if the defaults are not right for you:

| Variable | Default | Purpose |
|---|---|---|
| `SCHEDULE_TIME` | `08:00` | Local time to send the digest |
| `SCHEDULE_TIMEZONE` | `America/Los_Angeles` | IANA timezone for the schedule |
| `SCHEDULED_WINDOW_HOURS` | `24` | How far back each scheduled search looks |

Example values:

```text
SCHEDULE_TIME=08:00
SCHEDULE_TIMEZONE=America/New_York
SCHEDULED_WINDOW_HOURS=24
```

### 6. Enable And Test The Workflow

Open the repo's **Actions** tab. If GitHub asks you to enable workflows for the fork, enable them.

Then run **Topic Monitor Daily Digest -> Run workflow** once. Manual runs use `--force`, so they send immediately instead of waiting for 8:00 AM.

---

## Agent-Guided Setup

After installing the skill, ask your agent:

```text
/topic-monitor setup github-actions
```

The agent should guide you through:

- Confirming your fork/repo is the one that will run Actions.
- Choosing a send time; default is **8:00 AM**.
- Choosing a timezone; default is `America/Los_Angeles`.
- Confirming or adding at least one enabled topic in `subscriptions.md`.
- Collecting the names of required secrets and directing you to enter the values in GitHub Secrets.
- Optionally using interactive `gh secret set ...` commands so secrets are typed into GitHub CLI prompts, not pasted into chat.
- Setting optional GitHub Variables for schedule time and timezone.
- Running the workflow manually once to verify email delivery.

The agent should not ask you to paste long-lived API keys or Gmail App Passwords into chat unless you explicitly accept that risk. Prefer GitHub's secret UI or interactive GitHub CLI prompts.

---

## Using GitHub CLI Instead Of The Web UI

If `gh` is installed and authenticated, you can set secrets interactively from the repo root:

```bash
gh secret set GEMINI_API_KEY
gh secret set GMAIL_SENDER
gh secret set GMAIL_APP_PASSWORD
gh secret set EMAIL_RECIPIENTS
gh secret set TWITTER_API_KEY       # optional
```

Set or update schedule variables:

```bash
gh variable set SCHEDULE_TIME --body "08:00"
gh variable set SCHEDULE_TIMEZONE --body "America/Los_Angeles"
gh variable set SCHEDULED_WINDOW_HOURS --body "24"
```

Run a test digest:

```bash
gh workflow run "Topic Monitor Daily Digest"
```

---

## Usage

### One-Off Search

```text
/topic-monitor openAI
/topic-monitor "bay area startups"
```

### Manage Followed Topics

```text
/topic-monitor follow claude code
/topic-monitor unfollow xai
/topic-monitor pause adobe
/topic-monitor resume adobe
/topic-monitor list
```

`follow` only updates `subscriptions.md`. If this is your first topic or your fork has not sent a cloud digest yet, run `/topic-monitor setup github-actions` once so your agent can guide you through GitHub Secrets, schedule Variables, and a manual Actions test run.

### Manage Recipients For Cloud Digest

For GitHub Actions, update the `EMAIL_RECIPIENTS` repository secret. For local/manual config files, these commands can still update `config.md`:

```text
/topic-monitor set recipients add friend@gmail.com
/topic-monitor set recipients remove friend@gmail.com
/topic-monitor set recipients you@gmail.com, colleague@gmail.com
```

### Twitter/X

```text
/topic-monitor set twitter openAI on
/topic-monitor set twitter on
```

Remember to add `TWITTER_API_KEY` in GitHub Secrets before enabling Twitter-backed topics.

### Testing

```text
/topic-monitor test run
/topic-monitor test email
```

For cloud delivery, the most realistic test is the GitHub Actions manual run because it uses the same Secrets and runner environment as the daily digest.

---

## Source Scoring Rubric

Each source is scored across 4 dimensions (max 2.5 each = 10 total):

| Dimension | Criteria |
|---|---|
| Recency | <=1 day = 2.5; <=7 days = 2.0; <=30 days = 1.5; <=6 months = 1.0 |
| Authority | Reuters/BBC/NYT/arXiv = 2.5; TechCrunch/Wired = 2.0; Other = 1.0 |
| Engagement | Google News inclusion = 1.5; Twitter engagement scored 0.5-2.5 |
| Depth | >=800 words = 2.5; >=400 = 2.0; >=100 = 1.5; unknown = 1.0 |

Score thresholds: 8-10 feature prominently; 6-7.5 include; 4-5.5 include with caveat; <4 flag.

---

## File Structure

```text
topic-monitor/
├── .github/workflows/daily.yml  # GitHub Actions cloud scheduler
├── SKILL.md                     # Agent workflow instructions
├── README.md                    # User setup guide
├── config.example.md            # Optional local config template
├── subscriptions.md             # Followed topics; safe to edit and commit
├── scripts/
│   ├── run_daily.py             # Scheduled digest entry point
│   ├── run_search.py            # Manual search entry point
│   ├── search.py                # Google News RSS fetcher + scorer
│   ├── twitter_search.py        # TwitterAPI.io fetcher + scorer
│   └── send_email.py            # Gmail SMTP sender
└── references/
    ├── github-actions.md        # Agent setup guide for cloud scheduling
    ├── output-format.md         # Manual note template
    ├── source-scoring.md        # Scoring rubric reference
    └── user-guide.md            # Full command reference
```

---

## Security

This repository should never contain real API keys, Gmail App Passwords, or private credential files.

Secrets are intentionally read from GitHub Actions Secrets or local gitignored files:

- `GEMINI_API_KEY` or local `gemini_api_key`
- `GMAIL_SENDER` or local `gmail_sender`
- `GMAIL_APP_PASSWORD` or local `gmail_app_password`
- `EMAIL_RECIPIENTS` or local `config.md`
- `TWITTER_API_KEY` or local `twitter_api_key`

The following local files are gitignored and must stay uncommitted:

```text
config.md
gemini_api_key
gmail_app_password
gmail_sender
twitter_api_key
logs/
last_sent_date
```

Before pushing changes, you can check tracked files with:

```bash
git grep -n "GMAIL_APP_PASSWORD\|GEMINI_API_KEY\|TWITTER_API_KEY" -- .
```

Seeing placeholder names is expected. Seeing real secret values is not.

---

## AI Synthesis

Uses Gemini with a model fallback chain:

1. `gemini-3.1-flash-lite-preview`
2. `gemini-2.5-flash-lite`
3. `gemini-3-flash-preview`
4. `gemini-2.5-flash`

Cost is usually tiny on the Gemini free tier for a small daily digest.

---

## License

MIT
