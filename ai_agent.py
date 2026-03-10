import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
CALENDLY_BOOKING_URL = os.environ.get("CALENDLY_BOOKING_URL", "")

_BOOKING_INSTRUCTION = (
    f"\n- Always include this booking link so the prospect can schedule a viewing directly: {CALENDLY_BOOKING_URL}"
    if CALENDLY_BOOKING_URL else ""
)

SYSTEM_PROMPT = f"""You are a senior property consultant at Your Estate Agency. Write a reply to the inbound email below.

Rules:
- Sound like a real person, not a chatbot. No "Certainly!", "Absolutely!", "I hope this email finds you well", or any other filler phrases.
- Keep it short — 2–3 paragraphs max. Get to the point quickly.
- Use the sender's first name once at the start, then drop it.
- Respond directly to what they actually asked. If they mentioned a specific property, address it. If they didn't, ask one focused clarifying question.
- Never invent property details, prices, or availability.{_BOOKING_INSTRUCTION}
- Sign off with exactly:
  "Kind regards,

  Your Estate Agency"
"""


def is_genuine_enquiry(sender_email: str, subject: str, body: str) -> bool:
    """Classify whether an email is a genuine customer property enquiry.

    Uses a fast Claude call (no thinking, minimal tokens) to decide whether
    the email warrants a reply. Returns False for newsletters, job alerts,
    automated notifications, and marketing emails.

    Args:
        sender_email: The sender's email address.
        subject: The email subject line.
        body: The email body (will be truncated for speed).

    Returns:
        True if the email is a genuine human enquiry, False otherwise.
    """
    snippet = body[:500]

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=5,
        system=(
            "You classify inbound emails for an estate agency. "
            "Reply with only YES or NO, nothing else."
        ),
        messages=[{
            "role": "user",
            "content": (
                "Is this a genuine human enquiry about a property or estate agent services? "
                "Answer NO if it is a newsletter, job alert, promotion, automated notification, "
                "or any non-personal bulk email.\n\n"
                f"From: {sender_email}\n"
                f"Subject: {subject}\n"
                f"Body: {snippet}"
            ),
        }],
    )

    return response.content[0].text.strip().upper().startswith("YES")


def generate_reply(sender_name: str, subject: str, body: str) -> str:
    """Generate a personalised estate agent reply to an inbound email.

    Args:
        sender_name: Display name of the email sender (used to address them by name).
        subject: Subject line of the original email.
        body: Plain-text body of the original email.

    Returns:
        A ready-to-send reply as a plain-text string.
    """
    user_message = (
        f"Sender name: {sender_name}\n"
        f"Subject: {subject}\n\n"
        f"Email body:\n{body}"
    )

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1024,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        response = stream.get_final_message()

    return next(block.text for block in response.content if block.type == "text")
