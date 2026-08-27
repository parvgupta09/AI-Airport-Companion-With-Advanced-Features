# ✈️ AI Airport Companion

An **autonomous, agentic AI terminal companion** for passengers — powered by **Google Gemini**, **LangGraph**, **RAG**, **WebSockets**, and a full **Voice I/O** pipeline. Deployed on AWS.

---

## 🌐 What It Does

A passenger registers their PNR and the system:

1. **Generates** a full synthetic flight itinerary (airline, gate, terminal, baggage belt, layover)
2. **Auto-dispatches** a personalised magic link (email + SMS) 24 hours before boarding
3. **Unlocks** a stateful AI chat session 4 hours before departure via WebSocket
4. **Pushes** real-time alerts (gate changes, delays, boarding calls, reminders) via WebSocket — with Email/SMS fallback
5. **Answers** any terminal question using a multi-step agentic AI with tool calling and RAG
6. **Listens & speaks** via Sarvam AI STT + TTS (optimised for Indian accents & Hinglish)

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🔑 Passwordless Auth | Time-gated JWT magic links — active only within 4 hrs of departure |
| 🤖 Agentic AI | Gemini + LangGraph with intent routing, tool calling & conversation memory |
| 🗺️ Wayfinding | NetworkX dijkstra over a 100+ node airport graph (gates, shops, amenities) |
| 📚 RAG Policies | Qdrant vector DB + Gemini embeddings for airport rules & procedures |
| 🔔 Real-time Alerts | Redis Pub/Sub → WebSocket push with Email/SMS fallback |
| 🗣️ Voice I/O | Sarvam AI Saaras v3 (STT) + Bulbul v3 (TTS) |
| 🏪 Retailer Panel | Shops post live promotional offers surfaced by the AI |
| ⚙️ Background Jobs | 5 APScheduler jobs: flight sim, reminders, weather, cleanup, magic link auto-dispatch |

---

## 🛠️ Tech Stack

`FastAPI` · `LangGraph` · `Google Gemini` · `Qdrant` · `PostgreSQL` · `Redis` · `Sarvam AI` · `SendGrid` · `Twilio` · `NetworkX` · `APScheduler` · `Docker`

---

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app, CORS, lifespan
│   ├── api/
│   │   ├── auth_routes.py       # Magic link request + verify
│   │   ├── flights_routes.py    # Registration + flight status
│   │   ├── chat_routes.py       # WebSocket, STT, TTS, headless chat
│   │   └── admin_routes.py      # Retailer + offers CRUD
│   ├── core/
│   │   ├── config.py            # Env var loading (fails fast if missing)
│   │   ├── security.py          # JWT creation/verify, bcrypt
│   │   ├── redis_client.py      # Async Redis pool
│   │   └── websocket_manager.py # WS registry + push
│   ├── database/
│   │   ├── postgres_models.py   # SQLAlchemy: User, Flight, Retailer, Reminder
│   │   └── postgres_session.py  # Engine + get_db()
│   ├── graph/
│   │   ├── graph.py             # LangGraph StateGraph
│   │   ├── state.py             # AgentState TypedDict
│   │   ├── nodes/               # router, llm, tool, static nodes
│   │   └── prompts/             # system, router, tool prompts
│   ├── tools/
│   │   ├── flight_tool.py       # get_flight_status()
│   │   ├── wayfinding_tool.py   # get_walking_directions() + find_nearby_amenities()
│   │   ├── qdrant_search_tool.py# search_airport_policies()
│   │   └── reminder_tool.py     # schedule_passenger_reminder()
│   ├── services/                # FlightGenerator, Simulator, STT, TTS, Email, SMS, Weather
│   └── jobs/                    # flight_poll, reminders, weather, notification, cleanup
├── data/
│   ├── maps/mega_airport_map.json   # Airport graph (nodes + edges)
│   ├── static/                      # airlines, airports, aircraft JSON
│   └── policies/                    # 9 Markdown docs ingested into Qdrant
├── scripts/ingest_qdrant.py         # One-time policy ingestion
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 🏗️ Architecture

```
Frontend (React)
    │ REST + WebSocket
    ▼
FastAPI Backend
    ├── LangGraph Agent (Gemini)
    │     router → llm → tools → llm → reply
    ├── APScheduler Background Jobs
    │     flight simulator · reminders · weather · cleanup
    └── Redis Pub/Sub Notification Pipeline
          → WebSocket push → Email/SMS fallback
    │
    ├── PostgreSQL (users, flights, offers, reminders, LangGraph checkpoints)
    ├── Redis     (pub/sub alerts, reminder ZSET, weather cache)
    └── Qdrant    (airport policy RAG)
```

---

## 🚀 Running Locally

### 1. Clone & enter backend

```bash
git clone https://github.com/parvgupta09/AI-Airport-Companion-With-Advanced-Features.git
cd AI-Airport-Companion-With-Advanced-Features/backend
```

### 2. Create virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> macOS: `brew install libpq` if psycopg2 fails. Ubuntu: `sudo apt-get install libpq-dev gcc`

### 4. Configure `.env`

```bash
cp .env.example .env
# Fill in your credentials (see .env.example for descriptions of every variable)
nano .env
```

### 5. Create the database

```bash
# Local PostgreSQL:
psql -U postgres -c "CREATE DATABASE airport_db;"

# Or use Supabase (free) — paste the Pooler URL into DATABASE_URL
```

> Tables are **auto-created** on first startup via `Base.metadata.create_all()`.

### 6. Ingest policies into Qdrant (one-time)

```bash
python scripts/ingest_qdrant.py
```

This embeds the 9 Markdown policy files and uploads them to your Qdrant collection.

### 7. Start the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 8. Verify

| URL | Expected |
|---|---|
| `http://localhost:8000/` | `{"status": "ONLINE"}` |
| `http://localhost:8000/health` | `{"status": "healthy"}` |
| `http://localhost:8000/docs` | Swagger UI with all endpoints |

---

## 🐳 Docker

```bash
cd backend/

# Build & run
docker-compose up --build

# Background
docker-compose up --build -d

# Logs
docker-compose logs -f backend
```

---

## 🧪 Quick API Examples

### Register a passenger
```bash
curl -X POST http://localhost:8000/api/flights/register \
  -H "Content-Type: application/json" \
  -d '{
    "pnr": "ABC123",
    "name": "Parv Gupta",
    "email": "parv@example.com",
    "phone_number": "+919876543210",
    "source": "DEL",
    "destination": "DXB",
    "departure_time_utc": "2026-09-01T10:00:00"
  }'
```

### Check flight status
```bash
curl http://localhost:8000/api/flights/status/ABC123
```

### Request magic link
```bash
curl -X POST http://localhost:8000/api/auth/request-magic-link \
  -H "Content-Type: application/json" \
  -d '{"pnr": "ABC123", "email": "parv@example.com"}'
```

### Verify magic link
```bash
curl "http://localhost:8000/api/auth/verify-magic-link?token=<JWT_FROM_EMAIL>"
# Returns: session_token, user_id, flight_id, thread_id
```

### WebSocket chat (using wscat)
```bash
npm install -g wscat
wscat -c "ws://localhost:8000/api/chat/ws?token=<SESSION_TOKEN>"

> {"message": "Show me cafes near Gate 7"}
< {"type":"chat_response","message":"Costa Coffee is 2 minutes away..."}

> {"message": "What are the baggage rules?"}
< {"type":"chat_response","message":"Economy carry-on is 7kg, max 55x40x20cm..."}

> {"message": "Remind me to go to duty-free in 15 minutes"}
< {"type":"chat_response","message":"Reminder set for 15 minutes from now."}
```

### Voice input (STT)
```bash
curl -X POST http://localhost:8000/api/chat/voice-input \
  -F "file=@recording.wav;type=audio/wav"
# Returns: {"success": true, "text": "Where is the nearest ATM?"}
```

### Text-to-speech
```bash
curl -X POST http://localhost:8000/api/chat/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Boarding at Gate 7.", "speaker": "shubh", "language_code": "en-IN"}' \
  --output response.wav
```

---

## ⚙️ Background Jobs

| Job | Runs every | Does |
|---|---|---|
| `poll_active_flights` | 10 seconds | Simulates flight events, publishes alerts to Redis |
| `process_reminders` | 5 seconds | Pops due Redis ZSET reminders, fires WS/SMS alerts |
| `fetch_airport_weather` | 1 hour | Caches destination weather in Redis (2hr TTL) |
| `dispatch_due_magic_links` | 15 minutes | Auto-sends magic links for flights entering 24hr window |
| `run_cleanup_job` | 24 hours | Purges expired users, LangGraph checkpoints, Redis keys |
| `notification_listener` | Continuous | Redis Pub/Sub → WebSocket push + Email/SMS fallback |

---

## 🔑 Key Environment Variables

See [`backend/.env.example`](backend/.env.example) for the full annotated list. The most important ones:

```env
DATABASE_URL=postgresql://...        # PostgreSQL connection
REDIS_URL=redis://...                # Redis connection
QDRANT_URL=https://...               # Qdrant Cloud
QDRANT_API_KEY=...
QDRANT_COLLECTION_NAME=airport-policies
GEMINI_API_KEY=...                   # Google AI Studio
SARVAM_API_KEY=...                   # Sarvam AI (STT + TTS)
SENDGRID_API_KEY=...                 # Email
TWILIO_ACCOUNT_SID=...               # SMS
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
OPENWEATHER_API_KEY=...
JWT_SECRET=...                       # Min 32 chars
FRONTEND_URL=http://localhost:5173
ENVIRONMENT=development
```

---

*Built with Google Gemini · LangGraph · FastAPI · Sarvam AI · Redis · Qdrant*
