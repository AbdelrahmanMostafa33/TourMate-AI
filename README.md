<div align="center">

# 🧳 TourMate AI

**AI-Powered Personalized Travel Planning Assistant**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B?style=for-the-badge&logo=flutter&logoColor=white)](https://flutter.dev)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Framework-FF6F00?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![Groq](https://img.shields.io/badge/Groq-LLM_Inference-000000?style=for-the-badge)](https://groq.com)
[![Firebase](https://img.shields.io/badge/Firebase-Auth-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)](https://firebase.google.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)

*TourMate AI generates personalized, multi-day travel itineraries through natural conversation — powered by a modular AI pipeline that understands your travel personality.*

[Features](#-features) · [Architecture](#-architecture) · [Getting Started](#-getting-started) · [API Reference](#-api-reference) · [Tech Stack](#%EF%B8%8F-tech-stack) · [Team](#-team)

</div>

---

## 📖 Overview

TourMate AI is a smart travel planning application that combines **behavioral profiling**, **multi-agent AI orchestration**, and **multimodal input** (text + images) to generate highly personalized travel itineraries.

Instead of browsing generic travel guides, users simply **chat** with TourMate — describe their ideal trip in natural language, upload inspiring photos, and receive a complete day-by-day itinerary tailored to their unique travel personality.

### What Makes TourMate Different?

- 🧠 **Behavioral Profiling** — Learns your travel style through an onboarding flow and adapts over time
- 🤖 **6-Stage Pipeline** — Profile Loader → Place Retriever → Candidate Scorer → Planner → Route Optimizer → Itinerary Validator, orchestrated via LangGraph
- 🖼️ **Multimodal Input** — Gemini 2.5 Flash VLM understands both text and images to extract travel preferences
- 🗺️ **Real-World Data** — PostgreSQL-backed place database with Bayesian popularity scores + OSRM routing
- 💬 **Message Interpreter** — Single context-aware LLM call handles intent, slot extraction, and responses
- 🔄 **Adaptive Personalization** — Redis-backed session memory with conversation state machine

---

## ✨ Features

### 🔐 Authentication & Access
- Email/Password and Google OAuth via Firebase
- Password reset with email verification
- Role-based access control (user/admin)

### 🧬 Intelligent Profiling
- Onboarding personality flow (travel style, budget, interests, pace, accommodation, dining)
- AI-generated travel persona (e.g., "The Curious Culture Seeker")
- Per-trip behavioral profiles stored in PostgreSQL
- Profile-aware itinerary personalization

### 💬 Multimodal Chat
- Real-time WebSocket-based chat interface
- Message Interpreter — single structured-output LLM call for intent + extraction
- Gemini VLM image analysis for travel preference extraction
- Conversation state machine: GREETING → SLOT_FILLING → PLAN_GENERATION → ITINERARY_REVIEW
- Redis-backed session persistence with automatic TTL

### 🗓️ AI Itinerary Generation
- 6-stage LangGraph pipeline:
  - **Profile Loader** — Loads user behavioral profile from DB
  - **Place Retriever** — Filters places using SQL-style criteria from PostgreSQL
  - **Candidate Scorer** — Scores candidates with multi-signal formula + diversity
  - **Planner** — Generates day-by-day itinerary via LLM (Gemini 2.5 Flash)
  - **Route Optimizer** — Reorders stops using OSRM routing + 2-opt
  - **Itinerary Validator** — Programmatic feasibility + LLM quality checks (Groq Llama 3.1 8B)
- Automatic retry loop when validation fails

### 📍 Places & Exploration
- Database of real Cairo POIs (restaurants, attractions, hotels)
- Bayesian popularity scores per category
- Place search with filtering and sorting
- Save and review places

### 📊 Transparency & Learning
- Full agent decision logging with agent_messages trace
- LangSmith observability for agent execution tracing
- User feedback collection on completed plans
- Token usage tracking across all LLM calls

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Flutter Mobile App                         │
│      (Chat UI · Itinerary View · Trips · Auth)       │
└───────────────────┬──────────────────┬───────────────────────┘
                    │ REST API         │ WebSocket
                    ▼                  ▼
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐ │
│  │ Auth │ │Users │ │Trips │ │Places│ │Reviews│ │  Images  │ │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘ │
│     │        │        │        │        │           │        │
│  ┌──┴────────┴────────┴────────┴────────┴───────────┴─────┐  │
│  │              WebSocket Manager (ws/)                    │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           │                                  │
│  ┌────────────┐ ┌─────────┴──────┐ ┌──────────────────────┐ │
│  │ PostgreSQL │ │   AI Engine    │ │      Redis           │ │
│  │ Users/     │ │  (ai_engine/)  │ │  Sessions + Cache    │ │
│  │ Trips/     │ │                │ │                      │ │
│  │ Places/    │ │                │ │                      │ │
│  │ Reviews    │ │                │ │                      │
│  └────────────┘ └────────┬───────┘ └──────────────────────┘ │
└───────────────────────────┼──────────────────────────────────┘
                            │
           ┌────────────────▼────────────────┐
           │        Orchestrator              │
           │  (Message Interpreter + State)  │
           └────────────────┬────────────────┘
                            │
           ┌────────────────▼────────────────┐
           │      LangGraph Pipeline          │
           │                                  │
           │  load_profile → retrieval        │
           │  → ranking → planner             │
           │  → optimizer → validator         │
           │      └───────────┬───────────────┘│
           │                  │ (retry loop)   │
           │                  └──→ planner     │
           │                                  │
           │  External: Gemini · Groq · OSRM  │
           └──────────────────────────────────┘
```

### AI Models — Dual Provider Setup

| Provider | Model | Role | Use Case |
|----------|-------|------|----------|
| **Google Gemini** | Gemini 2.5 Flash | Planning + Vision | Itinerary generation, image understanding |
| **Groq** | Llama 3.3 70B Versatile | Router + Review QA | Unified routing, itinerary review Q&A |
| **Groq** | Llama 3.1 8B Instant | Fast Classification | Preference extraction, validation |

Both providers support **multi-key rotation** with automatic rate-limit fallback.

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.11+
- **PostgreSQL** 14+
- **Redis** (for session management)
- **Flutter** 3.x (for mobile app)
- **Google Gemini API Key** — [Get one here](https://aistudio.google.com/apikey)
- **Groq API Key** — [Get one here](https://console.groq.com)
- **Firebase Project** — [Create one here](https://console.firebase.google.com)

### Backend Setup

```bash
# 1. Clone the repository
git clone https://github.com/AbdooMatrix/TourMate-AI.git
cd TourMate-AI/backend

# 2. Create virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 3. Install dependencies
pip install -e .

# 4. Set up environment variables
# Create .env file (see below)
```

Create a `.env` file in the `backend/` folder:

```env
# === Required ===
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/tourmate
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
GOOGLE_API_KEY=your-google-gemini-api-key
GROQ_API_KEY=your-groq-api-key
FIREBASE_CREDENTIALS=firebase-credentials.json

# === Optional (LangSmith tracing) ===
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls_your-langsmith-key
LANGCHAIN_PROJECT=tourmate-ai
```

```bash
# 5. Set up PostgreSQL database
createdb tourmate

# 6. Seed place data (optional)
python seed_places.py cairo
python seed_places.py alexandria

# 7. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with docs at `/docs`.

### Mobile App Setup

```bash
cd TourMate-AI/mobile

# 1. Install Flutter dependencies
flutter pub get

# 2. Generate code (freezed models, Retrofit clients)
dart run build_runner build --delete-conflicting-outputs

# 3. Configure Firebase
# Place google-services.json (Android) in android/app/
# Place GoogleService-Info.plist (iOS) in ios/Runner/

# 4. Run the app
flutter run
```

### Running Tests

```bash
cd TourMate-AI/backend

# Run all tests
pytest -v

# Run specific test file
pytest tests/unit/test_ai_engine/test_llm_client.py -v

# Run with print output visible
pytest -v -s

# Run a single test function
pytest tests/unit/test_ai_engine/test_llm_client.py::test_intent_plan_trip -v
```

---

## 📁 Project Structure

```
TourMate-AI/
├── backend/
│   ├── ai_engine/                    # 🤖 AI Layer
│   │   ├── agents/                   # Planning agent (LLM-based)
│   │   ├── services/                 # Pipeline services (retriever, scorer, optimizer, validator)
│   │   ├── chat/                     # Orchestrator + message interpreter
│   │   ├── graph/                    # LangGraph pipeline
│   │   ├── memory/                   # Redis session management
│   │   ├── tools/                    # External integrations
│   │   ├── vision/                   # Image analysis pipeline
│   │   ├── evaluation/               # Agent metrics & explainability
│   │   ├── observability/            # LangSmith tracing
│   │   ├── llm_config.py             # Multi-provider LLM registry + key rotation
│   │   └── constants.py              # Model names & session config
│   │
│   ├── app/                          # ⚙️ Backend Layer
│   │   ├── api/v1/routes/            # API endpoints (12 routers)
│   │   ├── core/                     # Config, DB, security
│   │   ├── external/                 # Gemini, OSRM clients
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   ├── schemas/                  # Pydantic request/response
│   │   ├── repositories/             # Database query abstraction
│   │   ├── services/                 # Business logic
│   │   └── ws/                       # WebSocket manager
│   │
│   └── tests/                        # 🧪 17+ unit tests, integration, e2e
│
└── mobile/                           # 🎨 Flutter App (feature-first)
    └── lib/
        ├── app/                      # App config + routing
        ├── core/                     # Network, errors, layout
        └── features/
            ├── auth/                 # Sign in/up, profile
            ├── chat/                 # WebSocket chat + cubit
            ├── trips/                # Trip management
            └── splash/               # Splash screen
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Orchestrator Architecture](docs/architecture/orchestrator-architecture.md) | AI conversation orchestrator — phase router, handlers, services, state machine, and testing strategy |

---

## 📡 API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/login` | Login (Firebase token) |

### User Profile

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/users/profile` | Get user persona |
| `GET` | `/api/v1/users/profile/full` | Get complete profile |

### Trips

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/trips/` | Create new trip |
| `GET` | `/api/v1/trips/` | List all user trips |
| `GET` | `/api/v1/trips/{trip_id}` | Get trip details |
| `GET` | `/api/v1/trips/{trip_id}/itinerary` | Get full itinerary |
| `PATCH` | `/api/v1/trips/{trip_id}/status` | Update trip status |

### Places

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/places/search` | Search places by criteria |
| `GET` | `/api/v1/places/city/{city}` | Get places by city |
| `GET` | `/api/v1/places/explore` | Explore nearby places |

### Reviews & Saved Places

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/reviews/` | Create a review |
| `GET` | `/api/v1/reviews/place/{place_id}` | Get reviews for a place |
| `DELETE` | `/api/v1/reviews/{review_id}` | Delete a review |
| `POST` | `/api/v1/saved-places/` | Save a place |
| `GET` | `/api/v1/saved-places/` | Get saved places |
| `DELETE` | `/api/v1/saved-places/{place_id}` | Unsave a place |

### Recommendations & Images

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/recommendations/trip/{trip_id}` | Get recommendations |
| `POST` | `/api/v1/recommendations/{id}/accept` | Accept recommendation |
| `POST` | `/api/v1/recommendations/{id}/reject` | Reject recommendation |
| `GET` | `/api/v1/images/trip/{trip_id}` | Get images for trip |
| `DELETE` | `/api/v1/images/{image_id}` | Delete image |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `WS` | `/api/v1/ws/chat/{trip_id}?token=xxx` | Chat for existing trip |
| `WS` | `/api/v1/ws/chat/new?token=xxx` | New trip via chat |
| `GET` | `/api/v1/chat/{trip_id}/history` | Get chat history |
| `DELETE` | `/api/v1/chat/{trip_id}/clear` | Clear chat history |

### WebSocket Message Types

```jsonc
// Client → Server
{ "message": "Plan me a 3-day trip to Cairo" }

// Server → Client
{ "type": "session", "data": { "session_id": "...", "phase": "slot_filling" } }
{ "type": "phase", "data": { "phase": "plan_generation" } }
{ "type": "text", "content": "Here's" }             // Streaming token
{ "type": "done", "data": null }                     // Response complete
{ "type": "error", "data": "message" }               // Error occurred
```

---

## 🛠️ Tech Stack

### Backend
- **FastAPI** — Async Python web framework
- **PostgreSQL** — Relational database with async SQLAlchemy
- **Redis** — Conversation session management + caching
- **Firebase Admin SDK** — Authentication
- **Alembic** — Database migrations (10+ versions)

### AI Engine
- **LangGraph** — Multi-agent orchestration framework
- **Google Gemini 2.5 Flash** — Planning (reasoning) + Vision (multimodal)
- **Groq Llama 3.3 70B** — Unified routing + review QA
- **Groq Llama 3.1 8B** — Fast classification + validation
- **LangChain** — LLM abstractions + structured output
- **LangSmith** — Agent execution tracing (optional)
- **OSRM** — Open-source routing engine + distance matrix

### Mobile (Flutter)
- **Flutter** — Cross-platform mobile framework
- **FlutterFire** — Firebase integration
- **flutter_bloc** — State management (Cubit pattern)
- **freezed** — Immutable data classes with union types
- **dio + retrofit** — Type-safe HTTP client
- **get_it** — Dependency injection
- **web_socket_channel** — Real-time chat communication

---

## 🧪 Testing

```bash
# Run all tests
pytest -v

# Run with output
pytest -v -s

# Run specific category
pytest tests/unit/ -v
pytest tests/integration/ -v

# Run specific file
pytest tests/unit/test_ai_engine/test_llm_client.py -v

# Stop on first failure
pytest -v -x
```

---

## 🔒 Security Notes

- Never commit `firebase-credentials.json` or `.env` files
- All API endpoints require Firebase Bearer token authentication
- WebSocket connections authenticated via token query parameter
- Database credentials stored only in environment variables
- API keys support multi-key rotation with automatic rate-limit fallback

---

## 📄 License

This project is developed as part of an academic capstone project.

---

## 👥 Team

| Role | Count | Responsibilities |
|------|-------|------------------|
| 🎨 Frontend | 2 | Flutter UI, FlutterFire integration |
| ⚙️ Backend | 2 | FastAPI, PostgreSQL, Firebase |
| 🤖 AI | 2 | LangGraph agents, Gemini/Groq integration, profiling |

---

<div align="center">

**Built with ❤️ by the TourMate AI Team**

</div>
