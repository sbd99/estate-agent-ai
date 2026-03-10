import email as email_lib
import imaplib
import os
import re
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

_NAME_RE = re.compile(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}$')


def _extract_name_from_body(body: str) -> str:
    lines = [line.strip() for line in body.strip().splitlines() if line.strip()]
    for line in reversed(lines):
        if _NAME_RE.match(line):
            return line
    return ""

from dotenv import load_dotenv

from models import EmailMessage

load_dotenv()

IMAP_HOST = os.environ.get("IMAP_HOST", "")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")

# Headers that reliably indicate bulk/automated mail
_BULK_HEADERS = {"list-unsubscribe", "list-id", "list-post", "list-help"}


def _get_imap() -> imaplib.IMAP4_SSL:
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    return conn


def _extract_body(msg: email_lib.message.Message) -> str:
    """Return plain-text body, falling back to HTML if no plain-text part."""
    if msg.is_multipart():
        # First pass: prefer text/plain
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
        # Second pass: fall back to text/html
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="replace")
    return ""


def _synthetic_labels(msg: email_lib.message.Message) -> list:
    """Return Gmail-style category labels inferred from email headers.

    Allows automation.py's heuristic filter to work without modification.
    """
    headers_present = {h.lower() for h in msg.keys()}
    if _BULK_HEADERS.intersection(headers_present):
        return ["CATEGORY_PROMOTIONS"]
    precedence = msg.get("Precedence", "").lower()
    if precedence in ("bulk", "list", "junk"):
        return ["CATEGORY_PROMOTIONS"]
    return []


def get_unread_emails(max_results: int = 10) -> list[EmailMessage]:
    """Fetch unread emails from the last 24 h via IMAP."""
    conn = _get_imap()
    conn.select("INBOX")

    since = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
    _, data = conn.search(None, f'(UNSEEN SINCE "{since}")')

    uids = data[0].split()
    # Take the most recent N, maintain newest-first order
    uids = list(reversed(uids[-max_results:]))

    emails: list[EmailMessage] = []

    for uid in uids:
        _, msg_data = conn.fetch(uid, "(RFC822)")
        if not msg_data or not msg_data[0]:
            continue

        raw = msg_data[0][1]
        msg = email_lib.message_from_bytes(raw)

        sender_name, sender_email = email_lib.utils.parseaddr(msg.get("From", ""))
        body = _extract_body(msg)

        # If the display name is missing, looks like an email, or is just initials, try the signature
        if not sender_name or "@" in sender_name or all(len(w) <= 1 for w in sender_name.split()):
            sender_name = _extract_name_from_body(body) or (sender_email.split("@")[0] if sender_email else "Unknown")

        emails.append(EmailMessage(
            gmail_id=uid.decode(),
            message_id=msg.get("Message-ID", uid.decode()),
            thread_id=msg.get("Thread-Index", uid.decode()),
            sender_name=sender_name,
            sender_email=sender_email,
            subject=msg.get("Subject", "(no subject)"),
            body=body,
            labels=_synthetic_labels(msg),
        ))

    conn.logout()
    return emails


def send_reply(original: EmailMessage, reply_body: str) -> str:
    """Send a plain-text reply via SMTP, preserving thread headers."""
    subject = original.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    mime_msg = MIMEText(reply_body, "plain", "utf-8")
    mime_msg["From"] = EMAIL_ADDRESS
    mime_msg["To"] = original.sender_email
    mime_msg["Subject"] = subject
    mime_msg["In-Reply-To"] = original.message_id
    mime_msg["References"] = original.message_id

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.sendmail(EMAIL_ADDRESS, original.sender_email, mime_msg.as_string())

    return original.message_id


def mark_as_read(gmail_id: str) -> None:
    """Mark an email as read by its IMAP UID."""
    conn = _get_imap()
    conn.select("INBOX")
    conn.store(gmail_id, "+FLAGS", "\\Seen")
    conn.logout()
