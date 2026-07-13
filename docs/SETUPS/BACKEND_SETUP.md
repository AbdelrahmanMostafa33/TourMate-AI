# TourMate AI — Backend Setup Guide

> Complete guide for setting up the backend from scratch after cloning the repo for the first time.
> 📖 **For the full project overview (features, architecture, API reference, tech stack), see the [main README](../../README.md).**

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [Python Virtual Environment](#3-python-virtual-environment)
4. [Install Dependencies](#4-install-dependencies)
5. [PostgreSQL Setup](#5-postgresql-setup)
6. [Redis Setup](#6-redis-setup)
7. [Firebase Setup](#7-firebase-setup)
8. [Environment Variables (.env)](#8-environment-variables-env)
9. [Run the Server](#9-run-the-server)
10. [Verify Everything Works](#10-verify-everything-works)
11. [Project Structure Overview](#11-project-structure-overview)
12. [Common Errors & Fixes](#12-common-errors--fixes)

---

## 1. Prerequisites

Make sure you have all of these installed before starting.

| Tool | Version | Download |
|------|---------|----------|
| Python | **3.11** (required) | https://www.python.org/downloads/release/python-3110/ |
| PostgreSQL | 15 or 16 | https://www.postgresql.org/download/ |
| Redis | Latest | https://github.com/tporadowski/redis/releases *(Windows)* |
| Git | Latest | https://git-scm.com/downloads |

### Verify installations

Open a terminal and run:

```bash
python --version       # Should print Python 3.11.x
psql --version         # Should print psql (PostgreSQL) 15.x or 16.x
redis-cli --version    # Should print redis-cli x.x.x
git --version          # Should print git version x.x.x
```

> ⚠️ **Python 3.11 is required.** The project uses `asyncpg` and `langgraph` which may behave differently on 3.12+.

---

## 2. Clone the Repository

```bash
git clone https://github.com/AbdooMatrix/TourMate-AI.git
cd TourMate-AI/backend
```

---

## 3. Python Virtual Environment

Always work inside a virtual environment to avoid package conflicts.

```bash
# Create the venv (inside the backend/ folder)
python -m venv venv

# Activate it
# On Windows (PowerShell):
venv\Scripts\Activate.ps1

# On Windows (CMD):
venv\Scripts\activate.bat

# On Linux / macOS:
source venv/bin/activate
```

You should now see `(venv)` at the start of your terminal prompt.

---

## 4. Install Dependencies

From the project root:

```bash
pip install -e .
```

This installs all dependencies defined in `pyproject.toml`, including:
- **FastAPI + Uvicorn** — web framework and server
- **SQLAlchemy + asyncpg** — async database ORM
- **Alembic** — database migrations
- **Pydantic / pydantic-settings** — data validation and `.env` loading
- **Redis** — caching and session management
- **Firebase Admin** — authentication
- **LangGraph + LangChain + Groq** — AI engine orchestration
- **langchain-google-genai** — Gemini LLM integration
- **Passlib + python-jose** — password hashing and JWT tokens

> For development tools (pytest, ruff), run: `pip install -e '.[dev]'`

---

## 5. PostgreSQL Setup

### Step 1 — Open psql as superuser

```bash
# Windows
psql -U postgres

# Linux/macOS
sudo -u postgres psql
```

> If `psql` is not recognized on Windows, add it to PATH:
> `C:\Program Files\PostgreSQL\16\bin` (adjust version number)

### Step 2 — Create the database user and database

Run these commands inside the psql shell:

```sql
-- Create a user for this project
CREATE USER tourmate_user WITH PASSWORD 'yourpassword';

-- Create the database owned by that user
CREATE DATABASE tourmate OWNER tourmate_user;

-- Grant full access
GRANT ALL PRIVILEGES ON DATABASE tourmate TO tourmate_user;

-- Exit psql
\q
```

> You can choose any username and password you want — just make sure they match your `.env` file in Step 8.

### Step 3 — Verify the connection

```bash
psql -U tourmate_user -d tourmate -h localhost -W
# Enter the password you set above
# You should see:   tourmate=#
# Type \q to exit
```

### Step 4 — Seed place data (optional)

The project includes a generalized seed script to populate the database with place data for any city:

```bash
# Seed Cairo places
python seed_places.py cairo

# Seed Alexandria places
python seed_places.py alexandria
```

This populates the `places` table with real POIs (restaurants, attractions, hotels) including Bayesian popularity scores and pre-generated embeddings.

---

## 6. Redis Setup

Redis is used for conversation session management and caching.

### Windows

1. Download the latest `.msi` from https://github.com/tporadowski/redis/releases
2. Install it — it will register as a Windows service automatically
3. Verify it's running:

```powershell
redis-cli ping
# Should respond: PONG
```

### Linux

```bash
sudo apt install redis-server
sudo systemctl start redis
redis-cli ping   # Should respond: PONG
```

### macOS

```bash
brew install redis
brew services start redis
redis-cli ping   # Should respond: PONG
```

---

## 7. Firebase Setup

The backend uses Firebase for user authentication.

1. Go to https://console.firebase.google.com
2. Open the TourMate project (ask the team for access) or create a new one
3. Go to **Project Settings → Service Accounts**
4. Click **Generate new private key** — this downloads a `.json` file
5. Rename that file to `firebase-credentials.json`
6. Place it in the `backend/` root folder (same level as `app/`)

> ⚠️ **Never commit this file to Git.** It is already in `.gitignore`.

---

## 8. Environment Variables (.env)

Create a file named `.env` in the `backend/` folder:

```bash
# On Windows (PowerShell)
New-Item -Name ".env" -ItemType File

# On Linux/macOS
touch .env
```

Paste the following content and fill in your own values:

```env
# === Database ===
# Replace tourmate_user and yourpassword with what you set in Step 5
DATABASE_URL=postgresql+asyncpg://tourmate_user:yourpassword@localhost:5432/tourmate

# === Redis ===
REDIS_URL=redis://localhost:6379/0

# === Firebase ===
FIREBASE_CREDENTIALS=firebase-credentials.json

# === Security ===
# Generate a random secret key — used for JWT signing
# You can run:  python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=paste-your-generated-secret-here

# === AI (Gemini) ===
# Get a free API key from https://aistudio.google.com/apikey
# Comma-separated for multiple keys: key1,key2,key3
GOOGLE_API_KEY=your-google-gemini-api-key-here

# === AI (Groq) ===
# Get a free API key from https://console.groq.com
# Comma-separated for multiple keys: key1,key2,key3
GROQ_API_KEY=your-groq-api-key-here

# === Backend ===
BACKEND_BASE_URL=http://localhost:8000

# === LangSmith (Observability — optional) ===
# Enable tracing to see agent execution in the LangSmith dashboard
# 1. Sign up at https://smith.langchain.com
# 2. Create a project called "tourmate-ai"
# 3. Copy your API key and paste below
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls_your-langsmith-api-key
LANGCHAIN_PROJECT=tourmate-ai
```

### Required vs Optional Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string |
| `REDIS_URL` | ✅ Yes | Redis connection for session management |
| `SECRET_KEY` | ✅ Yes | JWT signing key |
| `GOOGLE_API_KEY` | ✅ Yes | Gemini LLM for planning + vision |
| `GROQ_API_KEY` | ✅ Yes | Groq LLM for routing + validation |
| `FIREBASE_CREDENTIALS` | ✅ Yes | Firebase auth service account |
| `BACKEND_BASE_URL` | No | Defaults to `http://localhost:8000` |
| `LANGCHAIN_TRACING_V2` | No | Enables LangSmith tracing |
| `LANGCHAIN_API_KEY` | No | LangSmith API key (required if tracing enabled) |
| `LANGCHAIN_PROJECT` | No | LangSmith project name (defaults to "default") |

### Generate a SECRET_KEY

Run this once to get a secure random key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output into the `SECRET_KEY` field in your `.env`.

### API Key Rotation

Both `GOOGLE_API_KEY` and `GROQ_API_KEY` support **multiple comma-separated keys** for automatic rotation:

```env
GOOGLE_API_KEY=key1,key2,key3
GROQ_API_KEY=key1,key2,key3
```

When a key hits a rate limit (429), the system automatically switches to the next available key. This is useful for staying within free-tier limits.

---

## 9. Run the Server

Make sure your virtual environment is activated and you are inside the `backend/` folder:

```bash
uvicorn app.main:app --reload
```

On first startup, the server will automatically create all database tables. You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [...] using StatReload
INFO:     Started server process [...]
INFO:     Waiting for application startup.
[LangSmith] Tracing enabled — project: tourmate-ai
INFO:     Application startup complete.
```

---

## 10. Verify Everything Works

### Check the root endpoint

Open your browser or run:

```bash
curl http://localhost:8000/
```

Expected response:
```json
{"message": "TourMate Backend Running"}
```

### Check the interactive API docs

Open in your browser: http://localhost:8000/docs

You should see the FastAPI Swagger UI with all available routes grouped by:
- **Auth** — `/api/v1/auth/...`
- **Users** — `/api/v1/users/...`
- **Trips** — `/api/v1/trips/...`
- **Chat** — `/api/v1/chat/...`
- **Places** — `/api/v1/places/...`
- **Reviews** — `/api/v1/reviews/...`
- **Saved Places** — `/api/v1/saved-places/...`
- **Bookings** — `/api/v1/bookings/...`
- **Flights** — `/api/v1/flights/...`
- **Itinerary** — `/api/v1/itinerary/...`
- **Images** — `/api/v1/images/...`
- **Feedback** — `/api/v1/feedback/...`
- **Admin** — `/api/v1/admin/...`
- **Webhooks** — `/api/v1/webhooks/...`
- **Health** — `/health`

### Check database tables were created

```bash
psql -U tourmate_user -d tourmate -h localhost -W
```

Inside psql:
```sql
\dt
-- Should list tables: users, profiles, trips, chat_messages,
-- places, saved_places, reviews, recommendations, images,
-- bookings, feedback, trip_profiles, system_log, etc.
```

---

## 11. Project Structure Overview

> 📖 A full project structure tree with all files and descriptions is in the [main README](../../README.md#-project-structure).
> Below is a simplified view showing only the top-level backend layout:

```
backend/
├── app/               # FastAPI application (routes, models, services, WebSocket)
├── ai_engine/         # LangGraph AI pipeline (agents, graph, profiling, tools)
├── alembic/           # Database migrations
├── tests/             # Unit, integration, and e2e tests
├── seed_places.py     # City-agnostic POI seeding script
├── docs/              # Architecture slides
├── pyproject.toml     # Python dependencies
└── .env               # Environment variables (not in Git)
```

---

## 12. Common Errors & Fixes

### ❌ `ImportError: cannot import name 'build_trip_graph'`

The function name in `ai_engine/graph/graph_builder.py` doesn't match the import in `ai_engine/__init__.py`. Make sure the function is named `build_trip_graph` (not `build_graph`).

---

### ❌ `password authentication failed for user "..."`

Your `.env` credentials don't match PostgreSQL. Run:

```bash
psql -U postgres
ALTER USER tourmate_user WITH PASSWORD 'yourpassword';
\q
```

Make sure the username and password in your `.env` exactly match what's in PostgreSQL.

---

### ❌ `psql: command not found` (Windows)

Add PostgreSQL's bin folder to your PATH:

```powershell
$env:PATH += ";C:\Program Files\PostgreSQL\16\bin"
```

Change `16` to your installed version number.

---

### ❌ `redis.exceptions.ConnectionError`

Redis is not running. Start it:

```powershell
# Windows — start the Redis service
Start-Service Redis

# Linux
sudo systemctl start redis
```

---

### ❌ `ModuleNotFoundError: No module named 'app'`

You're running uvicorn from the wrong directory. Make sure you're inside the `backend/` folder:

```bash
cd TourMate-AI/backend
uvicorn app.main:app --reload
```

---

### ❌ `pydantic_settings.env_settings.EnvSettingsError` / missing env variable

Your `.env` file is missing a required key or has a typo. Double-check that all required keys in Step 8 are present with real values (no placeholders).

Required variables: `DATABASE_URL`, `SECRET_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`

---

### ❌ `No API keys configured for gemini` / `No API keys configured for groq`

Your `.env` is missing `GOOGLE_API_KEY` or `GROQ_API_KEY`. Both are required for the AI engine to function. Get free API keys from:
- Gemini: https://aistudio.google.com/apikey
- Groq: https://console.groq.com

---

### ❌ `[LangSmith] LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY not set`

You enabled tracing but forgot the API key. Either:
1. Add `LANGCHAIN_API_KEY=ls_...` to your `.env`, or
2. Set `LANGCHAIN_TRACING_V2=false` to disable tracing

---

## Quick-Start Checklist

Use this as a final checklist before asking for help:

- [ ] Python 3.11 installed and active in venv
- [ ] `pip install -e .` completed without errors
- [ ] PostgreSQL running and `tourmate` database created
- [ ] `psql -U tourmate_user -d tourmate -h localhost` connects successfully
- [ ] Redis running (`redis-cli ping` returns `PONG`)
- [ ] `firebase-credentials.json` placed in `backend/` root
- [ ] `.env` file created with all required variables filled in:
  - [ ] `DATABASE_URL`
  - [ ] `REDIS_URL`
  - [ ] `SECRET_KEY`
  - [ ] `GOOGLE_API_KEY`
  - [ ] `GROQ_API_KEY`
  - [ ] `FIREBASE_CREDENTIALS`
- [ ] Running uvicorn from inside the `backend/` folder
- [ ] `http://localhost:8000/` returns `{"message": "TourMate Backend Running"}`
- [ ] (Optional) LangSmith tracing works at https://smith.langchain.com

---

*Last updated: July 2026 — TourMate AI Team*
