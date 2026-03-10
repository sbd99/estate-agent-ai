import base64
import email as email_lib
import os
import re
from email.mime.text import MIMEText
from typing import Optional

_NAME_RE = re.compile(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}$')

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models import EmailMessage  # noqa: F401 — re-exported for backwards compat

# gmail.modify covers read + label/archive; gmail.send covers sending
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def _get_service():
    """Authenticate and return a Gmail API service client.

    On first run this opens a browser for OAuth consent and saves a token.json.
    On subsequent runs it reuses (and auto-refreshes) the saved token.
    """
    creds: Optional[Credentials] = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _extract_body(payload: dict) -> str:
    """Recursively extract the plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    # For multipart messages, prefer text/plain over text/html
    if mime_type.startswith("multipart/"):
        parts = payload.get("parts", [])
        # First pass: plain text
        for part in parts:
            if part.get("mimeType") == "text/plain":
                body = _extract_body(part)
                if body:
                    return body
        # Second pass: recurse into nested multipart or fall back to html
        for part in parts:
            body = _extract_body(part)
            if body:
                return body

    if mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    return ""


def _parse_sender(from_header: str) -> tuple[str, str]:
    """Parse a From header into (display_name, email_address).

    Handles both 'Name <email>' and bare 'email' formats.
    Falls back to the local part of the email address if no display name.
    """
    name, addr = email_lib.utils.parseaddr(from_header)
    prefix = addr.split("@")[0] if addr else ""
    return (name or prefix), addr


def _extract_name_from_body(body: str) -> str:
    """Scan the last 10 lines of an email body for a signature name.

    Looks for lines matching 'First Last' or 'First Middle Last' (title case).
    Returns the first match found, or empty string if none.
    """
    lines = [line.strip() for line in body.strip().splitlines() if line.strip()]
    for line in reversed(lines):
        if _NAME_RE.match(line):
            return line
    return ""


def get_unread_emails(max_results: int = 10) -> list[EmailMessage]:
    """Return the most recent unread emails from the inbox.

    Args:
        max_results: Maximum number of emails to fetch (default 10).

    Returns:
        List of EmailMessage dataclasses ordered newest-first.

    Raises:
        HttpError: If the Gmail API call fails.
    """
    service = _get_service()

    results = service.users().messages().list(
        userId="me",
        q="is:unread in:inbox newer_than:1d",
        maxResults=max_results,
    ).execute()

    message_refs = results.get("messages", [])
    emails: list[EmailMessage] = []

    for ref in message_refs:
        msg = service.users().messages().get(
            userId="me",
            id=ref["id"],
            format="full",
        ).execute()

        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}

        sender_name, sender_email = _parse_sender(headers.get("From", ""))
        body = _extract_body(msg["payload"])

        # If the display name is missing, looks like an email, or is just initials, try the signature
        if not sender_name or "@" in sender_name or all(len(w) <= 1 for w in sender_name.split()):
            sender_name = _extract_name_from_body(body) or (sender_email.split("@")[0] if sender_email else "Unknown")

        emails.append(EmailMessage(
            gmail_id=msg["id"],
            message_id=headers.get("Message-ID", msg["id"]),
            thread_id=msg["threadId"],
            sender_name=sender_name,
            sender_email=sender_email,
            subject=headers.get("Subject", "(no subject)"),
            body=body,
            labels=msg.get("labelIds", []),
        ))

    return emails


def send_reply(original: EmailMessage, reply_body: str) -> str:
    """Send a plain-text reply to an email, keeping it in the same thread.

    Args:
        original: The EmailMessage being replied to.
        reply_body: Plain-text content of the reply.

    Returns:
        The Gmail message ID of the sent reply.

    Raises:
        HttpError: If the Gmail API call fails.
    """
    service = _get_service()

    subject = original.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    mime_msg = MIMEText(reply_body, "plain")
    mime_msg["To"] = original.sender_email
    mime_msg["Subject"] = subject
    mime_msg["In-Reply-To"] = original.message_id
    mime_msg["References"] = original.message_id

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

    sent = service.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": original.thread_id},
    ).execute()

    return sent["id"]


def mark_as_read(gmail_id: str) -> None:
    """Remove the UNREAD label from a message.

    Args:
        gmail_id: The Gmail internal message ID (EmailMessage.gmail_id).

    Raises:
        HttpError: If the Gmail API call fails.
    """
    service = _get_service()
    service.users().messages().modify(
        userId="me",
        id=gmail_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()
