#!/usr/bin/env python3
"""
Email sender for topic-monitor daily digest.
Uses Gmail SMTP with an App Password (no OAuth needed).

Setup (one-time):
  1. Go to https://myaccount.google.com/apppasswords
  2. Create an app password for "Mail" / "Mac" (or any name)
  3. Copy the 16-character password
  4. Run: python3 send_email.py --setup
     (or paste into ~/.claude/skills/topic-monitor/gmail_app_password)

Usage:
  python3 send_email.py --to user@gmail.com --subject "..." --body "..." --html
"""

import sys
import argparse
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

CONFIG_DIR = Path.home() / ".claude" / "skills" / "topic-monitor"
APP_PASSWORD_FILE = CONFIG_DIR / "gmail_app_password"
SENDER_EMAIL_FILE = CONFIG_DIR / "gmail_sender"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def load_credentials() -> tuple[str | None, str | None]:
    """Returns (sender_email, app_password) or (None, None) if not configured."""
    sender = SENDER_EMAIL_FILE.read_text().strip() if SENDER_EMAIL_FILE.exists() else None
    password = APP_PASSWORD_FILE.read_text().strip() if APP_PASSWORD_FILE.exists() else None
    return sender, password


def save_credentials(sender: str, password: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SENDER_EMAIL_FILE.write_text(sender.strip())
    APP_PASSWORD_FILE.write_text(password.strip())
    APP_PASSWORD_FILE.chmod(0o600)
    SENDER_EMAIL_FILE.chmod(0o600)


def setup_interactive() -> bool:
    """Interactive first-run setup. Returns True if successful."""
    print("\n" + "="*60, file=sys.stderr)
    print("  Topic Monitor — Gmail Setup", file=sys.stderr)
    print("="*60, file=sys.stderr)
    print("""
To send daily digest emails automatically, you need a Gmail
App Password. This takes about 2 minutes to set up.

STEP 1: Enable 2-Step Verification (if not already on)
  → https://myaccount.google.com/security
  → Click "2-Step Verification" and follow the steps

STEP 2: Create an App Password
  → https://myaccount.google.com/apppasswords
  → Click "Select app" → choose "Mail"
  → Click "Select device" → choose "Other" → type "topic-monitor"
  → Click "Generate"
  → Copy the 16-character password shown (spaces don't matter)

STEP 3: Paste it below
""", file=sys.stderr)

    sender = input("Your Gmail address (e.g. you@gmail.com): ").strip()
    if not sender or "@" not in sender:
        print("[setup] Invalid email address.", file=sys.stderr)
        return False

    password = input("Paste your 16-character App Password: ").strip().replace(" ", "")
    if len(password) != 16:
        print(f"[setup] App password should be 16 characters, got {len(password)}. Check and retry.", file=sys.stderr)
        return False

    # Test the credentials
    print("\n[setup] Testing credentials...", file=sys.stderr)
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(sender, password)
        print("[setup] ✓ Credentials verified!", file=sys.stderr)
    except smtplib.SMTPAuthenticationError:
        print("[setup] ✗ Authentication failed. Double-check the app password and try again.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[setup] ✗ Connection failed: {e}", file=sys.stderr)
        return False

    save_credentials(sender, password)
    print(f"[setup] Credentials saved to {CONFIG_DIR}", file=sys.stderr)
    print("[setup] Gmail is now configured for topic-monitor daily digests.\n", file=sys.stderr)
    return True


def send_email(
    to: str,
    subject: str,
    body: str,
    html: bool = False,
    sender: str | None = None,
    password: str | None = None,
) -> bool:
    """Send an email. Returns True on success."""
    if not sender or not password:
        saved_sender, saved_password = load_credentials()
        sender = sender or saved_sender
        password = password or saved_password

    if not sender or not password:
        print("[send_email] Gmail not configured. Run: python3 send_email.py --setup", file=sys.stderr)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type, "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(sender, password)
            server.sendmail(sender, to, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        print("[send_email] Authentication failed. Re-run --setup to update credentials.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[send_email] Failed to send: {e}", file=sys.stderr)
        return False


def is_configured() -> bool:
    return APP_PASSWORD_FILE.exists() and SENDER_EMAIL_FILE.exists()


def main():
    parser = argparse.ArgumentParser(description="Send email via Gmail SMTP")
    parser.add_argument("--setup", action="store_true", help="Interactive first-run setup")
    parser.add_argument("--to", help="Recipient email")
    parser.add_argument("--subject", help="Email subject")
    parser.add_argument("--body", help="Email body (plain text or HTML)")
    parser.add_argument("--html", action="store_true", help="Treat body as HTML")
    parser.add_argument("--check", action="store_true", help="Check if Gmail is configured")
    args = parser.parse_args()

    if args.setup:
        success = setup_interactive()
        sys.exit(0 if success else 1)

    if args.check:
        if is_configured():
            sender, _ = load_credentials()
            print(f"configured:{sender}")
        else:
            print("not_configured")
        sys.exit(0)

    if not args.to or not args.subject or not args.body:
        parser.error("--to, --subject, and --body are required for sending")

    success = send_email(args.to, args.subject, args.body, html=args.html)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
