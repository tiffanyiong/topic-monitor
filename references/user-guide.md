# Topic Monitor — User Guide

## Commands

### Search & Follow

| Command | What it does |
|---|---|
| `/topic-monitor openAI` | One-off search for a keyword |
| `/topic-monitor follow openAI` | Add topic to daily subscription list |
| `/topic-monitor unfollow openAI` | Remove topic from daily subscription list |
| `/topic-monitor pause openAI` | Pause a topic without removing it |
| `/topic-monitor resume openAI` | Re-enable a paused topic |
| `/topic-monitor list` | Show all followed topics and their status |

### Settings

| Command | What it does |
|---|---|
| `/topic-monitor set schedule 8am PST` | Change daily digest time |
| `/topic-monitor set window 24h` | Change recency window (e.g. 12h, 24h, 48h, 7d) |
| `/topic-monitor set email you@gmail.com` | Change digest recipient email |
| `/topic-monitor set twitter on` | Enable Twitter for all subscriptions |
| `/topic-monitor set twitter off` | Disable Twitter globally |
| `/topic-monitor set twitter openAI on` | Enable Twitter for one specific topic |

### Setup

| Command | What it does |
|---|---|
| `/topic-monitor setup email` | Walk through Gmail App Password setup |
| `/topic-monitor setup twitter` | Walk through TwitterAPI.io key setup |
| `/topic-monitor test email` | Send a test email to verify Gmail is working |
| `/topic-monitor test run` | Dry-run today's digest without sending email |

---

## First-Time Setup: Gmail Email Delivery

To receive the daily digest in your inbox, you need to configure a Gmail App Password once. This takes about 2 minutes.

### Step 1 — Enable 2-Step Verification
If you haven't already:
1. Go to https://myaccount.google.com/security
2. Click **2-Step Verification** and follow the steps

### Step 2 — Create an App Password
1. Go to https://myaccount.google.com/apppasswords
2. Click **Select app** → choose **Mail**
3. Click **Select device** → choose **Other** → type `topic-monitor`
4. Click **Generate**
5. Copy the **16-character password** shown (spaces are fine to include)

### Step 3 — Save it to topic-monitor
Run this in Claude Code:
```
/topic-monitor setup email
```
Claude will ask for your Gmail address and the app password, test the connection, and save it securely to `~/.claude/skills/topic-monitor/gmail_app_password` (chmod 600, readable only by you).

---

## First-Time Setup: Twitter/X Search

To include Twitter posts in your digest:

1. Sign up at https://twitterapi.io (includes $1 free credit)
2. Copy your API key from the dashboard
3. Run in Claude Code:
   ```
   /topic-monitor setup twitter
   ```
   Claude will save it to `~/.claude/skills/topic-monitor/twitter_api_key` (chmod 600).

Then enable Twitter per topic:
```
/topic-monitor set twitter openAI on
```
Or globally:
```
/topic-monitor set twitter on
```

---

## Subscription File

Your subscriptions live at:
`~/.claude/skills/topic-monitor/subscriptions.md`

You can edit it directly. Format:
```yaml
- keyword: openAI
  enabled: true
  days: 1          # search window (days) — overrides global setting
  twitter: false   # include Twitter for this topic
```

Set `enabled: false` to pause a topic without deleting it.

---

## Config File

Settings live at:
`~/.claude/skills/topic-monitor/config.md`

```yaml
schedule_time: "08:00"              # 24h format
schedule_timezone: America/Los_Angeles
scheduled_window_hours: 24          # recency window for scheduled runs
manual_window_days: 30              # recency window for manual /topic-monitor runs
email_recipient: you@gmail.com
```

---

## Folder Structure (Obsidian)

Manual runs save to:
```
Research/Topic Monitor/
├── openAI/
│   ├── 2026-05-01.md
│   └── 2026-05-02.md
├── xai/
│   └── 2026-05-01.md
└── bay area start up/
    └── 2026-05-01.md
```

Scheduled (daily email) runs do not write to Obsidian — the email is the record.

---

## How Scheduling Works

The daily digest runs on **Anthropic's remote infrastructure** — it fires at your configured time even if your Mac is off or Claude Code is closed. It's a cloud cron job, not a local one.

The remote agent:
1. Reads your `subscriptions.md` and `config.md`
2. Runs `run_daily.py` for all enabled topics
3. Builds an HTML digest email
4. Sends it via Gmail SMTP to your configured address

To change the schedule time:
```
/topic-monitor set schedule 9am EST
```
Claude will update `config.md` and re-register the cron.
