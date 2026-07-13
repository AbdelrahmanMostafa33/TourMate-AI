<div align="center">

# 🧳 TourMate AI

**AI-Powered Personalized Travel Planning Assistant**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B?style=for-the-badge&logo=flutter&logoColor=white)](https://flutter.dev)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi_Agent-FF6F00?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-000000?style=for-the-badge)](https://groq.com)
[![Firebase](https://img.shields.io/badge/Firebase-Auth-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)](https://firebase.google.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Async-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-Sessions-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Stripe](https://img.shields.io/badge/Stripe-Sandbox-008CDD?style=for-the-badge&logo=stripe&logoColor=white)](https://stripe.com)
[![Amadeus](https://img.shields.io/badge/Amadeus-Flights-004990?style=for-the-badge)](https://developers.amadeus.com)

*TourMate AI generates personalized, multi-day travel itineraries through natural conversation — powered by a modular AI pipeline that understands your travel personality, with full booking and payment support.*

[Features](#-features) · [Architecture](#-architecture) · [Getting Started](#-getting-started) · [API Reference](#-api-reference) · [Tech Stack](#%EF%B8%8F-tech-stack) · [Team](#-team)

</div>

---

## 📖 Overview

TourMate AI is a smart travel planning application that combines **behavioral profiling**, **multi-agent AI orchestration**, **multimodal input** (text + images), **real-time chat**, and **Stripe-powered payments** to generate highly personalized travel itineraries with full booking capabilities.

Instead of browsing generic travel guides, users simply **chat** with TourMate — describe their ideal trip in natural language, upload inspiring photos, and receive a complete day-by-day itinerary tailored to their unique travel personality. Once the itinerary is approved, users can search and book flights (via Amadeus), select hotels, and complete payments — all within the same conversation.

### What Makes TourMate Different?

- 🧠 **Behavioral Profiling** — Learns your travel style through conversation and adapts over time
- 🤖 **6-Stage Pipeline** — Profile Loader → Place Retriever → Candidate Scorer → Planner → Route Optimizer → Itinerary Validator, orchestrated via LangGraph
- 🖼️ **Multimodal Input** — Gemini 2.5 Flash VLM understands both text and images to extract travel preferences
- 💬 **Real-Time Chat** — WebSocket-based streaming protocol with structured card rendering (itinerary, hotel options, flight options)
- 🗺️ **Real-World Data** — PostgreSQL-backed place database with Bayesian popularity scores + OSRM routing
- 🔄 **Delta-Based Editing** — Modify itineraries surgically (ADD/REMOVE/SWAP) without full regeneration
- ✈️ **Flight Booking** — Real-time Amadeus flight search with Stripe payment integration
- 🏨 **Independent Hotel Selection** — DB-backed hotel search decoupled from the itinerary pipeline (like flights)
- 💳 **Stripe Payments** — Sandbox payment processing with combined flight + hotel checkout
- 🎭 **Conversation State Machine** — 9-phase flow: GREETING → SLOT_FILLING → PLAN_GENERATION → ITINERARY_REVIEW → FLIGHT_SELECTION → HOTEL_SELECTION → BOOKING → COMPLETED (+ IMAGE_REVIEW)

---

## ✨ Features

### 🔐 Authentication & Access
- Email/Password and Google OAuth via Firebase
- Firebase token verification on all protected endpoints
- Role-based access control (user/admin)

### 🧬 Intelligent Profiling
- Per-trip behavioral profiles stored in PostgreSQL
- AI-generated travel preferences (budget, style, pace, interests, food, accommodation)
- Profile-aware itinerary personalization via TripProfile table
- Preference confidence tracking over multiple trips
- Automatic persona updates on trip approval

### 💬 Multimodal Chat (WebSocket)
- Real-time WebSocket-based chat with structured event protocol:
  - `RESPONSE_STARTED` — stream begins
  - `TEXT_DELTA` — streaming token-by-token text
  - `CARD` — structured card (itinerary, hotel, flight, booking, image features)
  - `RESPONSE_COMPLETED` — stream ends with canonical segments
  - `TRIP_CREATED`, `TRIP_APPROVED`, `ACTIONS_APPLIED`, `ITINERARY_UPDATED`
- Message Interpreter — single structured-output LLM call for intent + extraction (replaces 3-call pattern)
- Gemini 2.5 Flash VLM image analysis for travel preference extraction
- Conversation state machine with Redis-backed session persistence
- Automatic state recovery from PostgreSQL when Redis TTL expires
- Image upload with AI analysis and preference extraction

### 🗓️ AI Itinerary Generation
- 6-stage LangGraph pipeline:
  - **Profile Loader** — Loads user behavioral profile from DB or creates mock profile
  - **Place Retriever** — Filters places using SQL-style criteria + semantic interest-to-subcategory matching (LLM-powered)
  - **Candidate Scorer** — Multi-signal scoring (popularity, embedding similarity, proximity, rating, diversity)
  - **Planning Agent** — Generates day-by-day itinerary via Gemini 2.5 Flash with structured output
  - **Route Optimizer** — Reorders stops using OSRM routing + 2-opt local search
  - **Itinerary Validator** — Programmatic feasibility checks + LLM quality evaluation (Groq Llama 3.3 70B)
- Automatic retry loop with feedback when validation fails
- Progress reporting to Flutter UI during pipeline execution

### ✏️ Delta-Based Itinerary Editing
- Modify existing itineraries surgically (no full regeneration):
  - `REMOVE` — Delete a stop
  - `SWAP` — Replace one stop with another from the pool
  - `EXCHANGE` — Swap time slots between two stops
  - `ADD` — Insert new stops from the pool
  - `ADD_CATEGORY` — Add places of a specific category
  - `REORDER` — Change visit sequence within a day
  - `RE_THEME` — Update a day's theme
- Hybrid search for place addition (exact DB match → vector semantic search → pool vector search)
- Automatic post-edit route optimization
- Edit Classifier Agent routes modification requests to correct workflow
- Preference Reranker Agent handles vibe-change reinterpretations

### ✈️ Flight Booking (Amadeus Integration)
- Real-time flight search via Amadeus API
- City name → IATA code resolution (auto-resolve "Cairo" to "CAI")
- Round-trip auto-computation from trip duration
- Smart search: resolve city names + search in one call
- Stripe PaymentIntent integration for flight payment
- Cabin class filtering (Economy, Premium Economy, Business, First)
- Trip-aware flight context pre-fill (destination, dates, traveler count)

### 🏨 Hotel Selection (Independent Pipeline)
- DB-backed hotel search (decoupled from itinerary pipeline — like flights)
- Accommodation type filtering (hotel, hostel, resort, luxury)
- Preferred star class filtering
- Conversational hotel selection with option number/name parsing
- Dynamic accommodation type changes during selection

### 💳 Payment & Booking System
- **Stripe sandbox** payment processing with PaymentIntent creation
- Combined flight + hotel checkout in a single Stripe charge
- Simulated booking fallback when Stripe is unavailable
- Async payment flow: initiate → Stripe Payment Sheet → confirm-after-payment
- Stripe webhook handling (payment_intent.succeeded, payment_intent.payment_failed, charge.refunded)
- Receipt generation with line-item breakdown
- Full cancellation flow with payment refunds
- Trip-level payment status management

### 📍 Places & Exploration
- Database of curated POIs (restaurants, attractions, hotels) for multiple cities
- Bayesian popularity scores per category
- Pre-computed embeddings for semantic search
- Explore places with city, country, and category filters
- Place detail screen with category-specific details
- Semantic search using text embeddings and cosine similarity
- Accommodation type filtering

### ⭐ Reviews & Saved Places
- Rate and review places (one review per user per place)
- Review likes
- Bookmark places with personal notes
- View review history

### 🖼️ Image-Based Travel Inspiration
- Upload travel photos for AI analysis
- Extract travel style cues, interests, food preferences, pace, budget
- Confidence-based preference extraction (high/medium/low)
- Feature persistence with ImageFeature table
- Image review conversation phase (user confirms or rejects extracted preferences)

### 📊 Transparency & Observability
- Full agent decision logging with `agent_messages` trace
- LangSmith observability for agent execution tracing (optional)
- Token usage tracking across all LLM calls per agent role
- Agent metrics (latency, errors, calls) per pipeline step
- Human-readable explainability module (deterministic, LLM-free)
- Itinerary quality metrics (category diversity, interest alignment, pacing, geographic coverage)

### 📝 Feedback & Continuous Improvement
- User feedback collection on completed trips (thumbs up/down, rating, comment)
- Preference confidence tracking across multiple trips
- Automatic traveler persona updates from approved trips

### 🔧 Trip Lifecycle Management
- 10 trip statuses: `planning` → `itinerary_draft` → `awaiting_booking` → `booking_pending` → `payment_processing` → `payment_failed` → `booking_confirmed` → `active` → `completed` / `cancelled`
- Full trip cancellation cascade (all bookings cancelled, payments refunded)
- Conversation history persistence and retrieval
- Chat history clear with Redis state cleanup

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      Flutter Mobile App                           │
│  (Chat UI · Itinerary Cards · Trips · Explore · Auth · Payment)  │
└───────────────────┬──────────────────────┬───────────────────────┘
                    │ REST API             │ WebSocket
                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                                  │
│                                                                     │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┬─────────┐ │
│  │   Auth   │  Users   │  Trips   │  Places  │ Reviews  │ Flights │ │
│  │ Firebase │ Profile  │ 10-Phase │ Explore  │  Saved   │Amadeus  │ │
│  │   OAuth  │  CRUD    │ Lifecycle│ Semantic │  Places  │ +Stripe │ │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴─────────┘ │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┬─────────┐ │
│  │Bookings  │Images    │Feedback  │Itinerary │  Admin   │Webhooks │ │
│  │+Stripe   │AI Vision │  System  │ Approval │ Endpoints│  Stripe │ │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴─────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │          WebSocket Manager (ws/manager.py)                    │   │
│  │  Connection tracking · Lock per key · Generation counters    │   │
│  └────────────────────────────────┬─────────────────────────────┘   │
│                                   │                                  │
│  ┌────────────────────────────────┴─────────────────────────────┐   │
│  │                    AI Engine (ai_engine/)                      │   │
│  │                                                               │   │
│  │  ┌─────────────────────────────────────────────────────────┐  │   │
│  │  │  Conversation Orchestrator (orchestrator.py)             │  │   │
│  │  │  9-Phase State Machine · Message Interpreter (1 LLM)   │  │   │
│  │  │  Redis Session Manager · Auto-Recovery from DB          │  │   │
│  │  └─────────────────────────┬───────────────────────────────┘  │   │
│  │                            │                                  │   │
│  │  ┌─────────────────────────▼───────────────────────────────┐  │   │
│  │  │          LangGraph Pipeline (6 nodes + retry)            │  │   │
│  │  │                                                         │  │   │
│  │  │  load_profile → retrieval → ranking → planner →        │  │   │
│  │  │  optimizer → validator ←── retry loop ─────────────    │  │   │
│  │  │                                                         │  │   │
│  │  │  Agents: Planning · Modifier · Edit Classifier ·       │  │   │
│  │  │          Preference Reranker · Flight Selection ·      │  │   │
│  │  │          Hotel Selection                                │  │   │
│  │  └─────────────────────────┬───────────────────────────────┘  │   │
│  │                            │                                  │   │
│  │  ┌─────────────────────────▼───────────────────────────────┐  │   │
│  │  │  Post-Approval (outside graph):                         │  │   │
│  │  │  Approve → FLIGHT_SELECTION (Amadeus) →                │  │   │
│  │  │  HOTEL_SELECTION (DB) → BOOKING (Stripe) → COMPLETED   │  │   │
│  │  └─────────────────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │  PostgreSQL   │  │    Redis     │  │   External Services       │ │
│  │  Async SQLAlc.│  │  Sessions    │  │   · Gemini 2.5 Flash     │ │
│  │  · Users      │  │  Caches      │  │   · Groq Llama 3.3 70B  │ │
│  │  · Trips      │  │  Place Pool  │  │   · OSRM Routing Engine  │ │
│  │  · Places     │  │             │  │   · Amadeus Flights      │ │
│  │  · Reviews    │  │             │  │   · Stripe Sandbox       │ │
│  │  · Bookings   │  │             │  │   · Firebase Auth         │ │
│  │  · Images     │  │             │  │                          │ │
│  │  · Feedback   │  │             │  │                          │ │
│  └──────────────┘  └──────────────┘  └───────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### AI Models — Dual Provider Setup

| Provider | Model | Role | Use Case |
|----------|-------|------|----------|
| **Google Gemini** | Gemini 2.5 Flash | Planning + Vision | Itinerary generation, image understanding, modifications |
| **Groq** | Llama 3.3 70B Versatile | Router + Review QA | Unified routing, itinerary review Q&A, semantic matching |
| **Groq** | Llama 3.1 8B Instant | Fast Classification | Preference extraction, validation | 

Both providers support **multi-key rotation** with automatic rate-limit fallback via `key_manager.py`. When a key hits a 429 rate limit, the system automatically switches to the next available key.

### Conversation Phase Lifecycle (9 phases)

```
GREETING
    │ User connects
    ▼
SLOT_FILLING
    │ System collects: city, duration, interests
    ▼
PLAN_GENERATION
    │ LangGraph pipeline runs (6 nodes + retry loop)
    ▼
ITINERARY_REVIEW
    │ User can approve, modify, or ask questions
    ▼
FLIGHT_SELECTION
    │ Search flights via Amadeus, select or skip
    ▼
HOTEL_SELECTION
    │ DB-backed hotel search, user picks
    ▼
BOOKING
    │ Pay now (Stripe) or do it later
    ▼
COMPLETED
    └── Terminal state (read-only Q&A)

Optional: IMAGE_REVIEW phase inserted when user uploads a photo
```

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
- **Stripe Account** (sandbox) — [Create one here](https://stripe.com)
- **Amadeus API Key** — [Get one here](https://developers.amadeus.com)

### Backend Setup

```bash
# 1. Clone the repository
git clone https://github.com/AbdooMatrix/TourMate-AI.git
cd TourMate-AI

# 2. Create virtual environment (inside backend/)
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 3. Install dependencies
# pyproject.toml is at the project root, so run from there
cd ..
pip install -e .
cd backend

# 4. Set up environment variables
# Create .env file (see details below)
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

# === Optional but recommended ===
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
AMADEUS_CLIENT_ID=your-amadeus-id
AMADEUS_CLIENT_SECRET=your-amadeus-secret
BACKEND_BASE_URL=http://localhost:8000

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

# 4. Run the app
flutter run
```

See [SETUPS/BACKEND_SETUP.md](docs/SETUPS/BACKEND_SETUP.md) and [SETUPS/MOBILE_SETUP.md](docs/SETUPS/MOBILE_SETUP.md) for detailed setup guides.

---

## 📁 Project Structure

```
TourMate-AI/
├── backend/
│   ├── ai_engine/                        # 🤖 AI Engine (LangGraph)
│   │   ├── agents/                       # Specialized AI agents
│   │   │   ├── planning_agent.py         # LLM itinerary generation (Gemini 2.5 Flash)
│   │   │   ├── hotel_agent.py            # Hotel selection compatibility shim
│   │   │   ├── hotel_selection_agent.py  # DB-backed hotel search & selection
│   │   │   ├── itinerary_modifier_agent.py # Delta-based ADD/REMOVE/SWAP editing
│   │   │   ├── edit_classifier_agent.py  # Routes edits to correct workflow
│   │   │   ├── preference_reranker_agent.py # Vibe-change reinterpretation
│   │   │   └── flight_selection_agent.py # Conversational flight search & selection
│   │   ├── conversation/                 # Conversation handling
│   │   │   ├── orchestrator.py           # Main chat processing + phase routing
│   │   │   ├── message_interpreter.py    # Unified Router (1 LLM call with structured output)
│   │   │   ├── conversation_state.py     # 9-phase state machine (GREETING → COMPLETED)
│   │   │   └── redis_memory.py           # Redis-backed session persistence
│   │   ├── evaluation/                   # Agent metrics & explainability
│   │   │   ├── agent_metrics.py          # Latency/error tracking per pipeline step
│   │   │   ├── explainability.py         # Human-readable pipeline decision summaries
│   │   │   ├── feasibility_checker.py    # Time/distance feasibility checks
│   │   │   └── itinerary_metrics.py      # Itinerary quality metrics
│   │   ├── graph/                        # LangGraph pipeline
│   │   │   ├── state.py                  # TripState + TripProfile TypedDicts
│   │   │   ├── nodes.py                  # Agent node wrappers
│   │   │   ├── edges.py                  # Conditional routing logic
│   │   │   ├── graph_builder.py          # Graph assembly & compilation
│   │   │   └── progress.py              # Async progress queue for Flutter UI
│   │   ├── llm/                          # LLM configuration & key management
│   │   │   ├── config.py                 # AGENT_LLM_REGISTRY - provider/model mapping
│   │   │   ├── invoke.py                 # invoke_with_fallback - multi-key retry
│   │   │   ├── key_manager.py            # Multi-key rotation for rate-limit resilience
│   │   │   └── token_tracker.py          # Per-pipeline-run token consumption tracking
│   │   ├── observability/                # LangSmith tracing
│   │   │   ├── tracing.py                # @traced decorator + setup
│   │   │   └── metrics.py                # Production metrics collection
│   │   ├── profiling/                    # Behavioral profiling
│   │   │   ├── profile_updater.py        # Profile refinement from user choices
│   │   │   ├── preference_tracker.py     # Tracks preference changes over time
│   │   │   └── persona_updater.py        # Updates traveler persona from trip history
│   │   ├── prompts/                      # LLM prompt templates
│   │   │   └── vision_prompt.py          # Vision analysis prompt
│   │   ├── schemas/                      # Pydantic models for structured output
│   │   │   ├── planning_schema.py        # ItineraryPlan schema
│   │   │   └── vision_schema.py          # VisionFeatures schema
│   │   ├── services/                     # AI engine internal services
│   │   │   ├── place_retriever.py        # DB-based place filtering + semantic matching
│   │   │   ├── candidate_scorer.py       # Multi-signal scoring + diversity optimization
│   │   │   ├── route_optimizer.py        # 2-opt + OSRM routing + day rebalancing
│   │   │   ├── itinerary_validator.py    # Programmatic + LLM quality checks
│   │   │   ├── pool_manager.py           # Candidate pool coverage + hybrid search
│   │   │   ├── embedding_service.py      # Async embedding generation & similarity
│   │   │   ├── operations.py             # Category detection & semantic filtering
│   │   │   └── place_extractor.py        # Place name extraction for hybrid search
│   │   ├── tools/                        # Tool functions used by agents
│   │   │   ├── places_tool.py            # Place search (DB-backed)
│   │   │   ├── routing_tool.py           # OSRM routing + matrix
│   │   │   ├── profile_tool.py           # Profile loading (real + mock)
│   │   │   ├── haversine.py              # Distance calculations
│   │   │   ├── json_utils.py             # Safe JSON deserialization
│   │   │   └── slot_normalizer.py        # Deterministic slot normalization
│   │   ├── vision/                       # Image analysis pipeline
│   │   │   ├── image_analyzer.py         # Travel image understanding (Gemini 2.5 Flash VLM)
│   │   │   ├── feature_extractor.py      # Visual feature extraction & validation
│   │   │   └── multimodal_fusion.py      # Image + profile fusion
│   │   ├── constants.py                  # Model names, session config, timeouts
│   │   └── __init__.py
│   │
│   ├── app/                              # ⚙️ Backend Layer (FastAPI)
│   │   ├── api/v1/routes/                # 15 route handlers
│   │   │   ├── auth.py                   # Firebase registration & login
│   │   │   ├── users.py                  # User profile endpoints
│   │   │   ├── trips.py                  # Trip CRUD + status management
│   │   │   ├── chat.py                   # WebSocket chat + history + list
│   │   │   ├── places.py                 # Place search, explore, semantic search
│   │   │   ├── reviews.py                # Place reviews with likes
│   │   │   ├── saved_places.py           # Bookmark places
│   │   │   ├── images.py                 # Image management
│   │   │   ├── bookings.py               # Booking creation + payment flow
│   │   │   ├── flights.py                # Amadeus flight search + booking
│   │   │   ├── itinerary.py              # Itinerary retrieval
│   │   │   ├── feedback.py               # User feedback CRUD
│   │   │   ├── admin.py                  # Placeholder (empty — no admin routes yet)│   │   │   ├── webhooks.py               # Stripe webhook processing
│   │   │   └── health.py                 # Health check
│   │   ├── core/                         # Config, database, security
│   │   ├── external/                     # External API clients
│   │   │   ├── llm_client.py             # Legacy LLM client wrapper
│   │   │   └── osrm_client.py            # OSRM routing/distance matrix
│   │   ├── models/                       # SQLAlchemy ORM models (users, profiles, trips,
│   │   │                                 #   itineraries, places, reviews, bookings, payments,
│   │   │                                 #   receipts, images, chat, feedback)
│   │   ├── schemas/                      # Pydantic request/response models
│   │   ├── services/                     # Business logic layer
│   │   │   ├── auth_service.py           # Authentication logic
│   │   │   ├── booking_service.py        # Booking + Stripe payment flow
│   │   │   ├── chat_service.py           # Chat/conversation DB operations
│   │   │   ├── flight_service.py         # Amadeus flight search + booking
│   │   │   ├── itinerary_service.py      # Itinerary stop creation
│   │   │   ├── places_service.py         # Place search & exploration
│   │   │   ├── profile_service.py        # Trip profile + persona management
│   │   │   ├── image_service.py          # Image CRUD + feature persistence
│   │   │   └── feedback_service.py       # Feedback operations
│   │   ├── repositories/                 # Database query abstraction
│   │   ├── ws/                           # WebSocket manager
│   │   └── main.py                       # App entry point
│   │
│   ├── alembic/                          # Database migrations (31+ versions)
│   ├── tests/                            # Test suite
│   │   ├── unit/test_ai_engine/          # AI engine unit tests (20+ files)
│   │   ├── unit/test_services/           # Service layer tests
│   │   ├── unit/test_routes/             # API route tests
│   │   ├── integration/                  # Integration tests (20+)
│   │   └── e2e/                          # End-to-end tests
│   │
│   ├── seed_places.py                    # City-agnostic POI seed script│   └── docs/                             # Architecture slides (mermaid diagrams)│├── data/                                 # 🌍 Curated place data (Cairo, Alexandria, etc.)├── docs/                                 # 📐 Architecture diagrams & setup guides└── mobile/                               # 🎨 Flutter App
    └── lib/
        ├── app/                          # App config + routing + theme
        ├── core/                         # Network, errors, layout, design tokens
        └── features/
            ├── auth/                     # Sign in/up, profile management
            ├── chat/                     # WebSocket chat with cards
            ├── trips/                    # Trip management (list, detail, create)
            ├── explore/                  # Place browsing & discovery
            ├── places/                   # Place detail, reviews
            ├── saved/                    # Saved/bookmarked places
            ├── flights/                  # Flight search & booking
            ├── bookings/                 # Booking management
            ├── payments/                 # Stripe Payment Sheet
            └── splash/                   # Splash screen
```

---

## 📡 API Reference

> Once the backend is running, visit **[http://localhost:8000/docs](http://localhost:8000/docs)** for the interactive Swagger UI with full request/response schemas and the ability to test endpoints live.

The API is organized into the following route groups:

| Group | Base Path | Key Endpoints |
|-------|-----------|---------------|
| **Auth** | `/api/v1/auth/` | Register, login |
| **Users** | `/api/v1/users/` | Profile (get, update) |
| **Trips** | `/api/v1/trips/` | CRUD, status, cancel, itinerary, profile |
| **Chat** | `/api/v1/chat/` + WS `/api/v1/ws/chat/` | History, clear, WebSocket streaming |
| **Places** | `/api/v1/places/` | Explore, search, semantic search, details |
| **Reviews** | `/api/v1/reviews/` | CRUD, likes, by place |
| **Saved Places** | `/api/v1/saved-places/` | Save, list, unsave |
| **Flights** | `/api/v1/flights/` | Search (city/IATA), book, confirm, cancel |
| **Bookings** | `/api/v1/bookings/` | Create, payment, cancel, combined checkout |
| **Images** | `/api/v1/images/` | List, get, delete |
| **Feedback** | `/api/v1/feedback/` | CRUD, by trip |
| **Webhooks** | `/api/v1/webhooks/` | Stripe event processing |
| **Health** | `/health` | Health check |

### WebSocket Protocol

The chat WebSocket uses a structured event protocol:

| Event | Direction | Description |
|-------|-----------|-------------|
| `RESPONSE_STARTED` | → | Stream begins |
| `TEXT_DELTA` | → | Token-by-token text |
| `CARD` | → | Structured card (itinerary, hotel, flight, booking) |
| `RESPONSE_COMPLETED` | → | Stream ends with canonical segments |
| `TRIP_CREATED` / `TRIP_APPROVED` / `ACTIONS_APPLIED` / `ITINERARY_UPDATED` | → | Lifecycle events |
| `ping` / `pong` | ↔ | Heartbeat |

> 🔐 Most endpoints require a Firebase Bearer token in the `Authorization` header. Public endpoints (explore, flight search) are marked in Swagger.

---

## 🛠️ Tech Stack

### Backend
- **FastAPI** — Async Python web framework
- **PostgreSQL** — Relational database with async SQLAlchemy + Alembic (31+ migrations)
- **Redis** — Conversation session management + candidate pool caching
- **Firebase Admin SDK** — Authentication via JWT verification
- **Stripe SDK** — Sandbox payment processing with webhook support
- **Amadeus SDK** — Real-time flight search and booking

### AI Engine
- **LangGraph** — Multi-agent orchestration framework (6-node pipeline + retry loop)
- **Google Gemini 2.5 Flash** — Planning (reasoning) + Vision (multimodal) + Modifications
- **Groq Llama 3.3 70B** — Unified routing + review QA + semantic matching
- **Groq Llama 3.1 8B** — Fast classification + validation
- **LangChain** — LLM abstractions + structured output
- **LangSmith** — Agent execution tracing (optional)
- **OSRM** — Open-source routing engine + distance matrix
- **Key Rotation** — Multi-key automatic fallback for rate-limit resilience
- **Token Tracking** — Per-role token consumption tracking across all LLM calls

### Mobile (Flutter)
- **Flutter** — Cross-platform mobile framework with Material Design 3
- **FlutterFire** — Firebase Auth integration
- **flutter_bloc** — State management (Cubit pattern)
- **freezed** — Immutable data classes with union types
- **dio + retrofit** — Type-safe HTTP client
- **get_it** — Dependency injection
- **web_socket_channel** — Real-time chat with structured event protocol
- **flutter_stripe** — Stripe Payment Sheet integration
- **flutter_map** — Map display for places
- **image_picker** — Photo upload for AI analysis
- **shimmer** — Premium loading animations
- **google_fonts** — Inter font family

---

## 🧪 Testing

```bash
# Run all tests
cd backend
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

### Test Coverage Areas
- **AI Engine Unit Tests** (20+): Planning agent, candidate scorer, route optimizer, itinerary validator, message interpreter, hotel agent, flight selection, edit classifier, preference reranker, embedding, pool management, session management, vision, operations, explainability, metrics
- **Service Layer Tests**: Auth, profile, Amadeus client, booking webhooks, state snapshot, Redis sync
- **API Route Tests**: Trips, users
- **Integration Tests** (20+): Full pipeline, itinerary creation, hotel flow, flight routes, feedback, reviews, places, semantic search, traveler persona, trip profile, candidate pool
- **Mobile Tests**: Chat WebSocket, message assembler, itinerary data, booking payment cubit, trip deletion flow

---

## 🔒 Security Notes

- Never commit `firebase-credentials.json` or `.env` files
- All API endpoints (except public browsing) require Firebase Bearer token authentication
- WebSocket connections authenticated via token query parameter
- Database credentials stored only in environment variables
- API keys support multi-key rotation with automatic rate-limit fallback
- Stripe webhook signature verification for payment events
- All payments run in Stripe sandbox (test mode) — no real financial transactions

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
