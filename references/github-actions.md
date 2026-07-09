# GitHub Actions Cloud Scheduling

Use this workflow when Topic Monitor should send daily email without depending on a user's laptop. This is the default automation path.

## Behavior

- `.github/workflows/daily.yml` runs on GitHub-hosted runners.
- The cron trigger wakes hourly in UTC.
- `scripts/run_daily.py --respect-schedule` checks `SCHEDULE_TIME` and `SCHEDULE_TIMEZONE`.
- The default schedule is **8:00 AM every day** in `America/Los_Angeles`.
- Manual workflow dispatch uses `--force` and sends immediately for testing.
- Credentials are read from GitHub Secrets, never from committed files.
- Topics are read from `subscriptions.md`.

## Required Secrets

Ask the user to enter these in **Settings -> Secrets and variables -> Actions -> Secrets** or through interactive `gh secret set` prompts. Do not ask for secret values in chat by default.

| Secret | Prompt the user for |
|---|---|
| `GEMINI_API_KEY` | Gemini API key from https://aistudio.google.com/apikey |
| `GMAIL_SENDER` | Gmail address that sends the digest |
| `GMAIL_APP_PASSWORD` | Gmail App Password, not the regular Gmail password |
| `EMAIL_RECIPIENTS` | Comma-separated recipients, e.g. `you@gmail.com,friend@gmail.com` |

Optional:

| Secret | Prompt the user for |
|---|---|
| `TWITTER_API_KEY` | TwitterAPI.io key, only needed for topics with `twitter: true` |

## Schedule Variables

Prompt the user for these values and use defaults when they do not care:

| Variable | Default | Prompt |
|---|---|---|
| `SCHEDULE_TIME` | `08:00` | What time should the digest send each day? |
| `SCHEDULE_TIMEZONE` | `America/Los_Angeles` | What timezone should that time use? |
| `SCHEDULED_WINDOW_HOURS` | `24` | How far back should scheduled searches look? |

Use IANA timezone names such as `America/Los_Angeles`, `America/New_York`, `Europe/London`, or `Asia/Shanghai`.

## Agent Setup Checklist

When a user asks `/topic-monitor setup github-actions`:

1. Confirm they are using their own fork/repo.
2. Confirm `.github/workflows/daily.yml` exists.
3. Confirm `subscriptions.md` has at least one enabled topic; prompt for a first keyword if needed.
4. Ask for schedule preferences; default to 8:00 AM and `America/Los_Angeles`.
5. Direct them to set required secrets in GitHub Secrets.
6. Direct them to set schedule values in GitHub Variables.
7. Prefer interactive CLI commands if `gh` is authenticated:

```bash
gh secret set GEMINI_API_KEY
gh secret set GMAIL_SENDER
gh secret set GMAIL_APP_PASSWORD
gh secret set EMAIL_RECIPIENTS
gh secret set TWITTER_API_KEY
gh variable set SCHEDULE_TIME --body "08:00"
gh variable set SCHEDULE_TIMEZONE --body "America/Los_Angeles"
gh variable set SCHEDULED_WINDOW_HOURS --body "24"
```

8. Tell them to open the repo's Actions tab and enable workflows if GitHub asks.
9. Run **Topic Monitor Daily Digest -> Run workflow** once to test delivery.
10. Before any commit/push, verify no secret values are tracked.

## Security Rules

- Never commit real API keys, Gmail App Passwords, or sender credentials.
- Placeholder names like `GEMINI_API_KEY` are safe; real values are not.
- If a user pasted a real secret into chat or a tracked file, tell them to rotate that secret.
- Check `git status --short` before committing. Credential files should be untracked or ignored.
- Use `git grep` or `rg` over tracked files to look for accidental secret values before pushing.
