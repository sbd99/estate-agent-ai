import re
import sys
import time
from datetime import datetime

# Ensure Unicode characters in email subjects/bodies don't crash the terminal on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai_agent import generate_reply, is_genuine_enquiry
from email_handler import get_unread_emails, mark_as_read, send_reply
from stats import record_enquiry

DELAY_BETWEEN_EMAILS = 15  # seconds — avoids Anthropic token-per-minute rate limits

# Gmail category labels applied automatically by Gmail's filtering
PROMOTIONAL_LABELS = {
    "CATEGORY_PROMOTIONS",
    "CATEGORY_SOCIAL",
    "CATEGORY_UPDATES",
    "CATEGORY_FORUMS",
}

# Sender address patterns that are never genuine customer enquiries
_NO_REPLY_RE = re.compile(
    r"(noreply|no-reply|donotreply|do-not-reply|mailer-daemon|"
    r"notification|newsletter|marketing|unsubscribe|bounce|automailer)",
    re.IGNORECASE,
)


def _is_obviously_not_enquiry(email) -> bool:
    """Return True if heuristics alone are enough to discard this email."""
    if _NO_REPLY_RE.search(email.sender_email):
        return True
    if PROMOTIONAL_LABELS.intersection(email.labels):
        return True
    return False


def run(max_results: int = 10) -> dict:
    print("Fetching unread emails...")
    emails = get_unread_emails(max_results=max_results)

    if not emails:
        print("No unread emails found.")
        return {"processed": 0, "failed": 0, "errors": []}

    print(f"Found {len(emails)} unread email(s).\n")

    errors = []
    skipped = []

    for i, email in enumerate(emails, start=1):
        print(f"[{i}/{len(emails)}] From: {email.sender_name} <{email.sender_email}>")
        print(f"        Subject: {email.subject}")

        # Step 1: fast heuristic filter (no API call)
        if _is_obviously_not_enquiry(email):
            print("        Skipping (promotional/automated — heuristic).\n")
            skipped.append({"sender_email": email.sender_email, "subject": email.subject, "reason": "heuristic"})
            continue

        # Step 2: AI classification for ambiguous emails
        try:
            if not is_genuine_enquiry(email.sender_email, email.subject, email.body):
                print("        Skipping (not a genuine enquiry — AI filter).\n")
                skipped.append({"sender_email": email.sender_email, "subject": email.subject, "reason": "ai_filter"})
                continue
        except Exception as e:
            print(f"        WARNING: AI filter failed ({e}), processing anyway.\n")

        # Step 3: generate reply, send, mark as read
        try:
            print("        Generating AI reply...")
            reply = generate_reply(
                sender_name=email.sender_name,
                subject=email.subject,
                body=email.body,
            )

            print("        Sending reply...")
            send_reply(email, reply)

            print("        Marking as read...")
            mark_as_read(email.gmail_id)

            record_enquiry(email.sender_name, email.sender_email, email.subject, "replied")
            print("        Done.\n")
        except Exception as e:
            print(f"        ERROR: {e} — skipping.\n")
            errors.append({
                "sender_name": email.sender_name,
                "sender_email": email.sender_email,
                "subject": email.subject,
                "error": f"{type(e).__name__}: {e}",
            })
            record_enquiry(email.sender_name, email.sender_email, email.subject, "failed")

        if i < len(emails):
            time.sleep(DELAY_BETWEEN_EMAILS)

    succeeded = len(emails) - len(errors) - len(skipped)
    print(f"Automation complete. {succeeded} replied, {len(skipped)} skipped, {len(errors)} failed.")

    return {
        "processed": succeeded,
        "skipped": len(skipped),
        "failed": len(errors),
        "skip_details": skipped,
        "errors": errors,
    }


CHECK_INTERVAL_SECONDS = 5 * 60  # 5 minutes


def start_scheduler():
    """Run the automation on a loop, checking for new emails every 5 minutes.

    Runs immediately on start, then waits CHECK_INTERVAL_SECONDS between runs.
    Press Ctrl+C to stop.
    """
    print("Scheduler started. Checking every 5 minutes. Press Ctrl+C to stop.\n")
    while True:
        print(f"--- Run started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
        try:
            run()
        except Exception as e:
            print(f"Unexpected error during run: {e}")

        print(f"Next check in 5 minutes...\n")
        try:
            time.sleep(CHECK_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nScheduler stopped.")
            break


if __name__ == "__main__":
    start_scheduler()
