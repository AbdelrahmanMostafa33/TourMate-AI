# TourMate AI — Backend Setup Guide

> Complete guide for setting up the backend from scratch after cloning the repo for the first time.

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

```bash
pip install -r requirements.txt
```

This installs:
- **FastAPI + Uvicorn** — web framework and server
- **SQLAlchemy + asyncpg** — async database ORM
- **Alembic** — database migrations
- **Pydantic / pydantic-settings** — data validation and `.env` loading
- **Redis** — caching and session management
- **Firebase Admin** — authentication
- **LangGraph + LangChain + Groq** — AI engine
- **Passlib + python-jose** — password hashing and JWT tokens

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

---

## 6. Redis Setup

Redis is used for caching and conversation memory.

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

# === AI (Groq) ===
# Get a free API key from https://console.groq.com
GROQ_API_KEY=your-groq-api-key-here

# === Backend ===
BACKEND_BASE_URL=http://localhost:8000
```

### Generate a SECRET_KEY

Run this once to get a secure random key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output into the `SECRET_KEY` field in your `.env`.

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
- **Chat** — `/api/v1/...`

### Check database tables were created

```bash
psql -U tourmate_user -d tourmate -h localhost -W
```

Inside psql:
```sql
\dt
-- Should list tables: users, profiles, trips, chat_messages, etc.
```

---

## 11. Project Structure Overview

```
backend/
│
├── app/                        # FastAPI application
│   ├── api/v1/routes/          # Route handlers (auth, users, trips, chat)
│   ├── core/                   # Config, database engine, security
│   ├── models/                 # SQLAlchemy ORM models
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/               # Business logic layer
│   ├── external/               # Groq client and other external APIs
│   ├── ws/                     # WebSocket manager
│   └── main.py                 # App entry point and lifespan
│
├── ai_engine/                  # LangGraph AI engine (separate from app/)
│   ├── graph/                  # StateGraph: nodes, edges, builder, state
│   ├── profiling/              # Cold start and behavioral profiling
│   ├── chat/                   # Intent parsing and chat handling
│   ├── tools/                  # LangChain tools (profile, places, etc.)
│   ├── agents/                 # Planning, optimization, validation agents
│   └── __init__.py             # Public API — import only from here
│
├── tests/                      # Unit and integration tests
├── .env                        # Your local environment variables (not in Git)
├── firebase-credentials.json   # Firebase service account (not in Git)
├── requirements.txt            # Python dependencies
└── README.md
```

> **Important rule:** Code inside `app/` must **never** import directly from `ai_engine` submodules. Always import from `ai_engine` top-level only (e.g. `from ai_engine import build_trip_graph`).

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

Your `.env` file is missing a required key or has a typo. Double-check that all keys in Step 8 are present with real values (no placeholders).

---

## Quick-Start Checklist

Use this as a final checklist before asking for help:

- [ ] Python 3.11 installed and active in venv
- [ ] `pip install -r requirements.txt` completed without errors
- [ ] PostgreSQL running and `tourmate` database created
- [ ] `psql -U tourmate_user -d tourmate -h localhost` connects successfully
- [ ] Redis running (`redis-cli ping` returns `PONG`)
- [ ] `firebase-credentials.json` placed in `backend/` root
- [ ] `.env` file created with all 6 variables filled in
- [ ] Running uvicorn from inside the `backend/` folder
- [ ] `http://localhost:8000/` returns `{"message": "TourMate Backend Running"}`

---

*Last updated: April 2026 — TourMate AI Team*
