# GitHub Actions Cloud Scheduling

Use this when you want Topic Monitor to send email even when your laptop is closed or turned off.

## How it works

- The workflow in `.github/workflows/daily.yml` runs in GitHub's cloud.
- GitHub cron wakes up hourly in UTC.
- `scripts/run_daily.py --respect-schedule` checks your configured `SCHEDULE_TIME` and `SCHEDULE_TIMEZONE`, then only sends during the matching local hour.
- Credentials are read from GitHub Secrets, not committed files.
- Topics are read from `subscriptions.md` in the repo.

## Required GitHub Secrets

Set these in your fork under **Settings -> Secrets and variables -> Actions -> New repository secret**:

| Secret | Value |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key from https://aistudio.google.com/apikey |
| `GMAIL_SENDER` | The Gmail address that sends the digest |
| `GMAIL_APP_PASSWORD` | A Gmail App Password, not your normal Gmail password |
| `EMAIL_RECIPIENTS` | Comma-separated recipients, e.g. `you@gmail.com,friend@gmail.com` |

Optional:

| Secret | Value |
|---|---|
| `TWITTER_API_KEY` | TwitterAPI.io key, only needed for topics with `twitter: true` |

## Optional GitHub Variables

Set these under **Settings -> Secrets and variables -> Actions -> Variables**:

| Variable | Default |
|---|---|
| `SCHEDULE_TIME` | `08:00` |
| `SCHEDULE_TIMEZONE` | `America/Los_Angeles` |
| `SCHEDULED_WINDOW_HOURS` | `24` |

## Setup Steps For Another User's Agent

When a user asks `/topic-monitor setup github-actions`, help them do this:

1. Confirm they have forked or cloned their own copy of the Topic Monitor repo.
2. Confirm `.github/workflows/daily.yml` exists. If not, copy it from this skill.
3. Confirm `subscriptions.md` has at least one enabled topic.
4. Guide them to add the required GitHub Secrets listed above.
5. Optionally set repository Variables for schedule time and timezone.
6. Ask them to open the repo's **Actions** tab and enable workflows if GitHub asks.
7. Run the workflow manually once with **Run workflow** to test delivery.
8. If they have `gh` installed and authenticated, offer CLI commands such as:

```bash
gh secret set GEMINI_API_KEY
gh secret set GMAIL_SENDER
gh secret set GMAIL_APP_PASSWORD
gh secret set EMAIL_RECIPIENTS
gh variable set SCHEDULE_TIME --body "08:00"
gh variable set SCHEDULE_TIMEZONE --body "America/Los_Angeles"
```

Do not ask users to paste long-lived secrets into chat unless they explicitly choose that tradeoff. Prefer GitHub's secret UI or interactive `gh secret set` prompts.
