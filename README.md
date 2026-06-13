# TourMate AI — README.md

Here's a comprehensive, professional README for your project:

```markdown
<div align="center">

# 🧳 TourMate AI

**AI-Powered Personalized Travel Planning Assistant**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B?style=for-the-badge&logo=flutter&logoColor=white)](https://flutter.dev)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Framework-FF6F00?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![Groq](https://img.shields.io/badge/Groq-LLM_Inference-000000?style=for-the-badge)](https://groq.com)
[![Firebase](https://img.shields.io/badge/Firebase-Auth-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)](https://firebase.google.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)

*TourMate AI generates personalized, multi-day travel itineraries through natural conversation — powered by a multi-agent AI system that understands your travel personality.*

[Features](#-features) · [Architecture](#-architecture) · [Getting Started](#-getting-started) · [API Reference](#-api-reference) · [Sprint Progress](#-sprint-progress) · [Team](#-team)

</div>

---

## 📖 Overview

TourMate AI is a smart travel planning application that combines **behavioral profiling**, **multi-agent AI orchestration**, and **multimodal input** (text + images) to generate highly personalized travel itineraries.

Instead of browsing generic travel guides, users simply **chat** with TourMate — describe their ideal trip in natural language, upload inspiring photos, and receive a complete day-by-day itinerary tailored to their unique travel personality.

### What Makes TourMate Different?

- 🧠 **Behavioral Profiling** — Learns your travel style through an onboarding quiz and adapts over time
- 🤖 **Multi-Agent Pipeline** — Planning, Optimization, and Validation agents collaborate via LangGraph
- 🖼️ **Multimodal Input** — Understands both text and images to extract travel preferences
- 🗺️ **Real-World Data** — Integrates Overpass API (POIs) and OSRM (routing) for realistic itineraries
- 💬 **Conversational Modifications** — Modify plans using natural language ("swap day 1 and 2", "add a museum")
- 🔄 **Adaptive Personalization** — Feedback loop refines recommendations with every interaction

---

## ✨ Features

### 🔐 Authentication & Access
- Email/Password and Google OAuth via Firebase
- Password reset with email verification
- Role-based access control (user/admin)

### 🧬 Intelligent Profiling
- Onboarding personality quiz (travel style, budget, interests, pace)
- AI-generated travel persona (e.g., "The Curious Culture Seeker")
- Behavioral profile stored and updated in PostgreSQL
- Profile-aware itinerary personalization

### 💬 Multimodal Chat
- Real-time WebSocket-based chat interface
- Natural language intent parsing (Llama 3.1 8B)
- Image analysis for travel preference extraction (Llama 4 Scout VLM)
- Clarifying questions when input is incomplete
- Persistent conversation history

### 🗓️ AI Itinerary Generation
- Multi-agent LangGraph pipeline:
  - **Planning Agent** — Generates raw itinerary using Llama 3.3 70B
  - **Optimization Agent** — Reorders stops using OSRM routing data
  - **Validation Agent** — Checks feasibility and time constraints
- Day-by-day itinerary with activities, times, locations, and notes
- Real POI data from Overpass API

### 📍 Booking Simulation
- Simulated accommodation and activity booking
- Trip confirmation and cancellation flows
- Natural language itinerary modification commands
- Trip library for upcoming and past plans

### 📊 Transparency & Learning
- Full agent decision logging
- User feedback collection on completed plans
- Feedback-driven behavioral profile refinement
- Data-driven insights dashboard

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Flutter Mobile App                         │
│         (Chat UI · Itinerary View · Profile · Explore)       │
└───────────────────┬──────────────────┬───────────────────────┘
                    │ REST API         │ WebSocket
                    ▼                  ▼
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │   Auth   │ │  Trips   │ │  Users   │ │     Chat       │  │
│  │ Firebase │ │   CRUD   │ │ Profiles │ │  WebSocket +   │  │
│  │          │ │          │ │  + Quiz  │ │  History       │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────┬────────┘  │
│                                                  │           │
│  ┌───────────────┐  ┌─────────────┐  ┌──────────▼────────┐  │
│  │  PostgreSQL   │  │   Firebase  │  │   AI Engine       │  │
│  │  Users/Trips  │  │   Storage   │  │   (ai_engine/)    │  │
│  │  Profiles     │  │   Images    │  │                   │  │
│  │  Conversations│  │             │  │                   │  │
│  └───────────────┘  └─────────────┘  └──────────┬────────┘  │
└──────────────────────────────────────────────────┼───────────┘
                                                   │
                    ┌──────────────────────────────▼───────────┐
                    │         LangGraph Pipeline                │
                    │                                          │
                    │  ┌────────┐   ┌───────────┐   ┌───────┐ │
                    │  │ Intent │──▶│  Profile  │──▶│ Plan  │ │
                    │  │ Parser │   │  Loader   │   │ Agent │ │
                    │  └────────┘   └───────────┘   └───┬───┘ │
                    │                                   │     │
                    │  ┌────────┐   ┌───────────┐       │     │
                    │  │Validate│◀──│ Optimize  │◀──────┘     │
                    │  │ Agent  │   │   Agent   │             │
                    │  └────────┘   └───────────┘             │
                    │                                          │
                    │  External: Groq API · Overpass · OSRM    │
                    └──────────────────────────────────────────┘
```

### AI Models (via Groq)

| Model | Purpose | Use Case |
|-------|---------|----------|
| **Llama 3.3 70B** | Planning & Generation | Itinerary creation, NL modifications |
| **Llama 3.1 8B** | Fast Classification | Intent parsing, validation |
| **Llama 4 Scout** | Vision (VLM) | Travel image analysis |

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.11+
- **PostgreSQL** 14+
- **Flutter** 3.x
- **Node.js** (for Firebase CLI, optional)
- **Groq API Key** — [Get one here](https://console.groq.com)
- **Firebase Project** — [Create one here](https://console.firebase.google.com)

### Backend Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/TourMate-AI.git
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
cp .env.example .env
```

Edit `.env` with your credentials:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/tourmate
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
groq_api_key=gsk_your_groq_api_key
FIREBASE_CREDENTIALS=firebase-credentials.json
```

> ⚠️ **Never commit `.env` or `firebase-credentials.json` to version control.**

```bash
# 5. Set up PostgreSQL database
createdb tourmate

# 6. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with docs at `/docs`.

### Frontend Setup

```bash
cd TourMate-AI/frontend

# 1. Install Flutter dependencies
flutter pub get

# 2. Configure Firebase
# Place google-services.json (Android) in android/app/
# Place GoogleService-Info.plist (iOS) in ios/Runner/

# 3. Run the app
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
│   │   ├── agents/                   # Agent implementations
│   │   ├── chat/                     # Chat handler + intent parser
│   │   │   ├── chat_handler.py       # Main chat processing
│   │   │   └── intent_parser.py      # NL intent classification
│   │   ├── evaluation/               # Agent metrics & explainability
│   │   ├── graph/                    # LangGraph pipeline
│   │   │   ├── state.py              # TripState + BehavioralProfile
│   │   │   ├── nodes.py              # Agent node functions
│   │   │   ├── edges.py              # Conditional routing logic
│   │   │   └── graph_builder.py      # Graph assembly & compilation
│   │   ├── memory/                   # Conversation memory (Redis)
│   │   ├── profiling/                # Behavioral profiling
│   │   │   ├── behavioral_profile.py # Profile-to-text helpers
│   │   │   └── cold_start.py         # Persona generation
│   │   ├── prompts/                  # LLM prompt templates
│   │   ├── tools/                    # External tool integrations
│   │   │   └── profile_tool.py       # Profile loading (mock + real)
│   │   ├── vision/                   # Image analysis pipeline
│   │   └── constants.py              # Model names & settings
│   │
│   ├── app/                          # ⚙️ Backend Layer
│   │   ├── api/v1/routes/            # API endpoints
│   │   │   ├── auth.py               # Registration & login
│   │   │   ├── chat.py               # WebSocket chat + history
│   │   │   ├── trips.py              # Trip CRUD
│   │   │   └── users.py              # Profile & quiz endpoints
│   │   ├── core/                     # Config, DB, security
│   │   ├── external/                 # Third-party clients
│   │   │   └── groq_client.py        # Groq API (planning/fast/vision)
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   ├── schemas/                  # Pydantic request/response
│   │   ├── services/                 # Business logic
│   │   ├── ws/                       # WebSocket manager
│   │   └── main.py                   # FastAPI app entry point
│   │
│   └── tests/                        # 🧪 Test Suite
│       ├── unit/
│       ├── integration/
│       └── e2e/
│
└── frontend/                         # 🎨 Flutter App
    └── lib/
```

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
| `POST` | `/api/v1/users/quiz` | Submit onboarding quiz |
| `POST` | `/api/v1/users/quiz/skip` | Skip quiz (default persona) |
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
{ "type": "typing" }                              // AI is thinking
{ "type": "token", "data": "Here's" }             // Streaming token
{ "type": "done" }                                 // Response complete
{ "type": "actions", "data": [...] }               // DB mutations
{ "type": "trip_created", "trip_id": "uuid" }      // New trip created
{ "type": "itinerary_updated" }                    // Itinerary changed
{ "type": "error", "data": "message" }             // Error occurred
```

---

## 🗓️ Sprint Progress

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 1 | Auth Setup | ✅ Complete |
| Sprint 2 | User Profiling | ✅ Complete |
| Sprint 3 | Multimodal Chat | 🔄 In Progress |
| Sprint 4 | Itinerary Engine | ⬜ Upcoming |
| Sprint 5 | Booking Simulation | ⬜ Upcoming |
| Sprint 6 | Explore & Profile | ⬜ Upcoming |
| Sprint 7 | Logging & Learning | ⬜ Upcoming |

---

## 🛠️ Tech Stack

### Backend
- **FastAPI** — Async Python web framework
- **PostgreSQL** — Relational database
- **SQLAlchemy** (async) — ORM
- **Firebase Admin SDK** — Authentication
- **Redis** — Conversation caching (planned)

### AI Engine
- **LangGraph** — Multi-agent orchestration framework
- **Groq API** — Ultra-fast LLM inference
  - Llama 3.3 70B (planning)
  - Llama 3.1 8B (classification)
  - Llama 4 Scout (vision)
- **LangChain** — LLM abstractions
- **Overpass API** — OpenStreetMap POI data
- **OSRM** — Open-source routing engine

### Frontend
- **Flutter** — Cross-platform mobile framework
- **FlutterFire** — Firebase integration
- **WebSocket** — Real-time chat communication

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

---

## 📄 License

This project is developed as part of an academic capstone project.

---

## 👥 Team

| Role | Count | Responsibilities |
|------|-------|------------------|
| 🎨 Frontend | 2 | Flutter UI, FlutterFire integration |
| ⚙️ Backend | 2 | FastAPI, PostgreSQL, Firebase |
| 🤖 AI | 2 | LangGraph agents, Groq integration, profiling |

---

<div align="center">

**Built with ❤️ by the TourMate AI Team**

</div>
```

---

## How to Use

Save this as `README.md` in your project root:

```
D:\Projects\TourMate-AI\README.md
```

### Also create `.env.example` (safe to commit):

```env
DATABASE_URL=postgresql://user:password@localhost:5432/tourmate
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=change-me-to-a-random-string
groq_api_key=gsk_your_key_here
FIREBASE_CREDENTIALS=firebase-credentials.json
```

### Update `.gitignore`:

```gitignore
# Secrets
.env
firebase-credentials.json
*.pem
*.key

# Python
__pycache__/
*.pyc
venv/
.pytest_cache/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```