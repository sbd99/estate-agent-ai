# Estate Agent AI — Claude Code Context

## What this project does
Gmail automation for Your Estate Agency. On each run it:
1. Fetches unread emails from the last 24 h
2. Discards promotional/automated mail via heuristics, then AI classification
3. Generates a personalised reply with Claude and sends it
4. Marks the email as read and records the outcome in `stats.json`

A FastAPI server exposes the pipeline as an API and serves a live dashboard at `GET /`.

---

## Stack
- **Python 3.12** — venv at `venv/`
- **FastAPI + uvicorn** — API server
- **Google Gmail API** — OAuth "installed app" flow (`credentials.json` / `token.json`)
- **Anthropic SDK** (`anthropic` 0.83.0) — Claude calls
- **python-dotenv** — loads `ANTHROPIC_API_KEY` from `.env`

---

## File map
| File | Purpose |
|------|---------|
| `main.py` | FastAPI app — all routes including dashboard, stats, automation trigger |
| `gmail_handler.py` | Gmail OAuth + `get_unread_emails` / `send_reply` / `mark_as_read` |
| `ai_agent.py` | `is_genuine_enquiry()` + `generate_reply()` via Claude |
| `automation.py` | End-to-end pipeline — can run standalone or be called by API |
| `stats.py` | Read/write `stats.json` — `record_enquiry`, `increment_bookings`, `get_stats` |
| `dashboard.html` | Single-page live dashboard; served at `GET /` |
| `stats.json` | Persisted run statistics (auto-created on first run) |
| `test_gmail.py` | Standalone Gmail connection smoke-test |
| `credentials.json` | Google OAuth client credentials — **keep secret** |
| `token.json` | Saved OAuth token (auto-refreshes) — **keep secret** |
| `.env` | `ANTHROPIC_API_KEY` + `CALENDLY_WEBHOOK_SECRET` — **keep secret** |

---

## API routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Live dashboard (HTML) |
| GET | `/stats` | Current stats JSON |
| POST | `/stats/booking` | Increment booking counter |
| POST | `/webhooks/calendly` | Calendly webhook — increments bookings on `invitee.created` |
| GET | `/health` | Health check |
| GET | `/emails/unread` | Fetch unread emails (`?max_results=10`) |
| POST | `/emails/reply` | Send a reply |
| POST | `/emails/{gmail_id}/read` | Mark as read |
| POST | `/emails/generate-reply` | Generate AI reply (no send) |
| POST | `/automation/run` | Trigger full pipeline (`?max_results=10`) |

---

## Key design decisions & gotchas

### EmailMessage has two ID fields
- `gmail_id` — Gmail's internal message ID; used for the modify API (`mark_as_read`)
- `message_id` — RFC 2822 `Message-ID` header; used for reply threading
- **Mixing these up causes 400 errors.**

### Gmail query
`is:unread in:inbox newer_than:1d` — limits to last 24 h to avoid processing old backlog.

### Rate limiting
`DELAY_BETWEEN_EMAILS = 15 s` in `automation.py` — keeps Anthropic usage under ~30 k tokens/min.

### Email filtering (two-stage)
1. Fast heuristics — no-reply address patterns + Gmail category labels (`CATEGORY_PROMOTIONS` etc.)
2. AI classification via `is_genuine_enquiry()` — only for emails that pass heuristics

### Stats persistence
`stats.py` writes to `stats.json` in the project root. Works cross-process (standalone script + API server both use it). `recent[]` is capped at 20 entries, newest first.

### Windows Unicode
`sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at the top of `automation.py` — required on Windows to handle emoji in email subjects/bodies.

### First OAuth run
Opens a browser window; `token.json` is saved afterwards and auto-refreshes.

---

## Models
| Use | Model | Notes |
|-----|-------|-------|
| `generate_reply` | `claude-opus-4-6` | `thinking: {type: "adaptive"}` |
| `is_genuine_enquiry` | `claude-opus-4-6` | `max_tokens=5`, no thinking |

---

## How to run

```bash
# Activate venv (Windows bash)
source venv/Scripts/activate

# Start API server
venv/Scripts/uvicorn.exe main:app --reload --port 8000

# Run automation directly (uses scheduler loop)
venv/Scripts/python.exe automation.py

# Smoke-test Gmail connection
venv/Scripts/python.exe test_gmail.py
```

Dashboard: `http://localhost:8000/` — polls `/stats` every 10 s automatically.
