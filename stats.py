import json
import os
from datetime import datetime

STATS_FILE = os.path.join(os.path.dirname(__file__), "stats.json")

_DEFAULT = {
    "total_enquiries": 0,
    "replies_sent": 0,
    "bookings": 0,
    "recent": [],
    "bookings_list": [],
}


def _load() -> dict:
    if not os.path.exists(STATS_FILE):
        return dict(_DEFAULT)
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Backfill any missing keys (e.g. after schema changes)
        for key, default in _DEFAULT.items():
            data.setdefault(key, default)
        return data
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT)


def _save(data: dict) -> None:
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def record_enquiry(
    sender_name: str,
    sender_email: str,
    subject: str,
    status: str,  # "replied" | "failed"
) -> None:
    """Record a processed enquiry and persist to disk."""
    data = _load()

    data["total_enquiries"] += 1
    if status == "replied":
        data["replies_sent"] += 1

    entry = {
        "sender_name": sender_name,
        "sender_email": sender_email,
        "subject": subject,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

    data["recent"].insert(0, entry)
    data["recent"] = data["recent"][:20]  # cap at 20

    _save(data)


def increment_bookings(name: str = "", email: str = "") -> int:
    """Increment the booking counter, optionally recording who booked."""
    data = _load()
    data["bookings"] += 1
    if name or email:
        entry = {
            "name": name or email.split("@")[0],
            "email": email,
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        data.setdefault("bookings_list", []).insert(0, entry)
        data["bookings_list"] = data["bookings_list"][:20]
    _save(data)
    return data["bookings"]


def get_stats() -> dict:
    return _load()
