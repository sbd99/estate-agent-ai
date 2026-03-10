"""Provider router — import email functions from here, not from gmail_handler directly.

Set EMAIL_PROVIDER=gmail (default) or EMAIL_PROVIDER=imap in your .env.
"""
import os

from dotenv import load_dotenv

load_dotenv()

_PROVIDER = os.environ.get("EMAIL_PROVIDER", "gmail").lower()

if _PROVIDER == "imap":
    from imap_handler import get_unread_emails, mark_as_read, send_reply
else:
    from gmail_handler import get_unread_emails, mark_as_read, send_reply

from models import EmailMessage

__all__ = ["get_unread_emails", "send_reply", "mark_as_read", "EmailMessage"]
