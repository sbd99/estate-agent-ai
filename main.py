import asyncio
import hashlib
import hmac
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import anthropic

from ai_agent import generate_reply
from automation import run as run_automation
from email_handler import EmailMessage, get_unread_emails, mark_as_read, send_reply
from stats import get_stats, increment_bookings

_DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")
_CALENDLY_SECRET = os.getenv("CALENDLY_WEBHOOK_SECRET", "")
_SCHEDULER_INTERVAL = 5 * 60  # seconds


async def _scheduler():
    """Background task: runs the automation pipeline every 5 minutes."""
    while True:
        print(f"[scheduler] Run started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            results = await asyncio.to_thread(run_automation)
            print(
                f"[scheduler] Done — {results['processed']} replied, "
                f"{results.get('skipped', 0)} skipped, {results['failed']} failed."
            )
        except Exception as e:
            print(f"[scheduler] Unexpected error: {e}")
        await asyncio.sleep(_SCHEDULER_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_scheduler())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)


def _verify_calendly_signature(raw_body: bytes, sig_header: str) -> None:
    """Raise 401 if the Calendly-Webhook-Signature header is invalid."""
    try:
        parts = dict(part.split("=", 1) for part in sig_header.split(",") if "=" in part)
        timestamp = parts["t"]
        received_sig = parts["v1"]
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Missing or malformed webhook signature")

    signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}"
    expected_sig = hmac.new(
        _CALENDLY_SECRET.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, received_sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open(_DASHBOARD_PATH, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/stats")
def stats():
    return get_stats()


@app.post("/stats/booking")
def add_booking():
    stats_data = get_stats()
    recent = stats_data.get("recent", [])
    name = recent[0]["sender_name"] if recent else ""
    email = recent[0]["sender_email"] if recent else ""
    new_total = increment_bookings(name=name, email=email)
    return {"bookings": new_total}


@app.post("/webhooks/calendly")
async def calendly_webhook(request: Request):
    raw_body = await request.body()

    if _CALENDLY_SECRET:
        sig_header = request.headers.get("Calendly-Webhook-Signature", "")
        _verify_calendly_signature(raw_body, sig_header)

    payload = json.loads(raw_body)
    event = payload.get("event")

    if event == "invitee.created":
        invitee = payload.get("payload", {})
        name = invitee.get("name", "")
        email = invitee.get("email", "")
        # Fall back to matching by email in recent enquiries
        if not name and email:
            match = next((r for r in get_stats().get("recent", []) if r["sender_email"] == email), None)
            if match:
                name = match["sender_name"]
        new_total = increment_bookings(name=name, email=email)
        return {"received": True, "event": event, "bookings": new_total}

    # Acknowledge all other events (invitee.canceled, routing_form_submission.created, etc.)
    return {"received": True, "event": event}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/emails/unread")
def fetch_unread_emails(max_results: int = Query(default=10, ge=1, le=50)):
    try:
        emails = get_unread_emails(max_results=max_results)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Email provider error: {e}")
    return [
        {
            "gmail_id": email.gmail_id,
            "message_id": email.message_id,
            "thread_id": email.thread_id,
            "sender_name": email.sender_name,
            "sender_email": email.sender_email,
            "subject": email.subject,
            "body": email.body,
            "labels": email.labels,
        }
        for email in emails
    ]


class ReplyRequest(BaseModel):
    gmail_id: str
    message_id: str
    thread_id: str
    sender_email: str
    subject: str
    reply_body: str


@app.post("/emails/reply")
def reply_to_email(payload: ReplyRequest):
    original = EmailMessage(
        gmail_id=payload.gmail_id,
        message_id=payload.message_id,
        thread_id=payload.thread_id,
        sender_name="",
        sender_email=payload.sender_email,
        subject=payload.subject,
        body="",
    )
    try:
        sent_id = send_reply(original, payload.reply_body)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Email provider error: {e}")
    return {"sent_message_id": sent_id}


@app.post("/emails/{gmail_id}/read")
def mark_email_as_read(gmail_id: str):
    try:
        mark_as_read(gmail_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Email provider error: {e}")
    return {"gmail_id": gmail_id, "status": "read"}


class GenerateReplyRequest(BaseModel):
    sender_name: str
    subject: str
    body: str


@app.post("/emails/generate-reply")
def generate_email_reply(payload: GenerateReplyRequest):
    try:
        reply = generate_reply(
            sender_name=payload.sender_name,
            subject=payload.subject,
            body=payload.body,
        )
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {e}")
    return {"reply": reply}


@app.post("/automation/run")
def trigger_automation(max_results: int = Query(default=10, ge=1, le=50)):
    results = run_automation(max_results=max_results)
    return results