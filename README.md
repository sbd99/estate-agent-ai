# Estate Agent AI — Gmail Automation

An AI-powered email automation system for estate agents. It monitors a Gmail inbox, filters out spam and promotional mail, generates personalised replies using Claude, sends them automatically, and tracks outcomes on a live web dashboard.

![Dashboard Screenshot](screenshot.png)

---

## How it works

```
Gmail Inbox
    │
    ▼
Stage 1 — Heuristic filter
(no-reply patterns, Gmail promotional labels)
    │
    ▼
Stage 2 — AI classification
Claude decides YES / NO: genuine enquiry?
    │
    ▼
Reply generation
Claude writes a personalised response
    │
    ▼
Send via Gmail API → Mark as read → Record to stats
    │
    ▼
Live Dashboard (auto-refreshes every 10s)
```

The pipeline runs automatically every **5 minutes** via a background scheduler built into the FastAPI server. It can also be triggered manually via the API or run as a standalone script.

---

## Features

- **Two-stage email filtering** — fast heuristics first, then AI classification, to avoid wasting tokens on obvious spam
- **AI reply generation** — Claude with adaptive thinking writes natural, personalised responses
- **Gmail OAuth integration** — full read, send, and label management via the Gmail API
- **Live dashboard** — real-time stats for enquiries received, replies sent, and viewings booked
- **Calendly webhook** — automatically increments the booking counter when a viewing is scheduled
- **REST API** — all functionality exposed as API endpoints via FastAPI
- **Background scheduler** — runs the full pipeline every 5 minutes without any manual intervention

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| API server | FastAPI + uvicorn |
| AI | Anthropic SDK — Claude (`claude-opus-4-6`) |
| Email | Google Gmail API (OAuth 2.0) |
| Scheduling | asyncio background task |
| Frontend | Vanilla JS single-page dashboard |
| Persistence | JSON file (`stats.json`) |

---

## Project structure

```
├── main.py            # FastAPI app — all routes + background scheduler
├── ai_agent.py        # Claude AI — classify enquiries + generate replies
├── automation.py      # End-to-end pipeline logic
├── email_handler.py   # Gmail OAuth, read / send / mark-as-read
├── models.py          # EmailMessage dataclass
├── stats.py           # Read/write stats.json
├── dashboard.html     # Live web dashboard
├── .env.example       # Environment variable template
└── stats.json         # Persisted stats (auto-created on first run)
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/estate-agent-ai.git
cd estate-agent-ai
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
source venv/Scripts/activate    # Windows (bash)
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```
ANTHROPIC_API_KEY=your-anthropic-api-key
CALENDLY_BOOKING_URL=https://calendly.com/your-username/30min
```

### 5. Set up Gmail API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Gmail API**
3. Create OAuth 2.0 credentials (Desktop app) and download as `credentials.json`
4. Place `credentials.json` in the project root

### 6. Run the server

```bash
uvicorn main:app --reload --port 8000
```

On first run, a browser window will open for Gmail OAuth consent. After authorising, `token.json` is saved and auto-refreshes from then on.

Open the dashboard at **http://localhost:8000/**

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Live dashboard |
| `GET` | `/stats` | Current stats JSON |
| `POST` | `/automation/run` | Trigger the full pipeline |
| `GET` | `/emails/unread` | Fetch unread emails |
| `POST` | `/emails/generate-reply` | Generate an AI reply (no send) |
| `POST` | `/emails/reply` | Send a reply |
| `POST` | `/emails/{gmail_id}/read` | Mark an email as read |
| `POST` | `/webhooks/calendly` | Calendly webhook |
| `GET` | `/health` | Health check |

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `CALENDLY_BOOKING_URL` | No | Calendly link included in replies |
| `EMAIL_PROVIDER` | No | `gmail` (default) or `imap` |

---

## Notes

- The scheduler processes up to 10 emails per run by default (configurable via `?max_results=`)
- A 15-second delay between emails keeps usage within Anthropic's rate limits
- `stats.json` is gitignored — it may contain sender names and email addresses
- `credentials.json` and `token.json` are gitignored — never commit these
