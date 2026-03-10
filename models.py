from dataclasses import dataclass, field


@dataclass
class EmailMessage:
    gmail_id: str      # Provider's internal message ID (Gmail ID or IMAP UID)
    message_id: str    # RFC 2822 Message-ID header, used for reply threading
    thread_id: str     # Thread/conversation ID
    sender_name: str
    sender_email: str
    subject: str
    body: str
    labels: list = field(default_factory=list)  # Gmail labels or synthetic equivalents
