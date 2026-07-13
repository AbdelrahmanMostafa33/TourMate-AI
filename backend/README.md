# TourMate AI — Backend

> 📖 For the full project overview, architecture, features, and API reference, see the **[main README](../README.md)**.

Backend service for the TourMate AI travel planning platform.

## Overview

The backend is a **FastAPI** application that powers:
- 🔐 **Authentication** via Firebase (email/password + Google OAuth)
- 🧬 **AI-powered itinerary generation** via a 6-stage LangGraph pipeline
- 💬 **Real-time chat** via WebSocket with structured streaming protocol
- ✈️ **Flight booking** via Amadeus API
- 🏨 **Hotel selection** from a curated database
- 💳 **Stripe payment** processing (sandbox mode)
- 📍 **Place discovery** with semantic search via embeddings
- ⭐ **Reviews** and **saved places**

## Quick Start

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -e .

# Set up .env (see docs/SETUPS/BACKEND_SETUP.md)
# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Key Modules

| Directory | Purpose |
|-----------|---------|
| `ai_engine/` | LangGraph AI pipeline — agents, graph, conversation, LLM config, vision |
| `app/api/v1/routes/` | 15 FastAPI route handlers |
| `app/core/` | Config, database engine, Firebase security, dependencies |
| `app/services/` | Business logic — bookings, flights, chat, places, images |
| `app/models/` | SQLAlchemy ORM models (10+ tables) |
| `app/schemas/` | Pydantic request/response models |
| `app/ws/` | WebSocket connection manager |
| `alembic/` | Database migrations (31+ versions) |
| `tests/` | Unit, integration, and e2e tests (50+ test files) |

## API Docs

Once running, visit `http://localhost:8000/docs` for the interactive Swagger UI.

## More Info

| Resource | Link |
|----------|------|
| 📖 **Main Project README** | [../README.md](../README.md) — architecture, features, API reference, tech stack |
| 🛠️ **Detailed Setup Guide** | [docs/SETUPS/BACKEND_SETUP.md](../docs/SETUPS/BACKEND_SETUP.md) — prerequisites, env vars, troubleshooting |
| 📱 **Mobile Component** | [../mobile/README.md](../mobile/README.md) — Flutter app overview |
