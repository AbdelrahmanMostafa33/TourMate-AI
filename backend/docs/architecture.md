# TourMate AI — Architecture Diagram

> **Legend:** `→` reads from TripState · `←` writes to TripState · `⇄` reads and writes

```mermaid
---
title: TourMate AI — Trip State, Profile & Agent Pipeline
---
flowchart TB
    subgraph TripProfile["📋 TripProfile (Per-Trip)"]
        direction LR
        TP_Budget["budget_level: budget / moderate / luxury"]
        TP_Style["travel_style: romantic / adventure / cultural / ..."]
        TP_Pace["pace: relaxed / moderate / packed"]
        TP_Interests["interests: [history, food, art, ...]"]
        TP_Food["food_preferences: [local cuisine, ...]"]
        TP_Accom["accommodation_preferences: [boutique hotel, ...]"]
    end

    subgraph TripState["🧠 TripState (Central Workflow State)"]
        direction TB
        
        subgraph Input["📥 Input"]
            MSG["user_message"]
            CTX["conversation_context"]
            TOK["token"]
            TID["trip_id"]
            DEST["destination_city"]
            DUR["duration_days"]
        end

        subgraph Profile_Box["👤 Profile"]
            PROF["profile → TripProfile"]
        end

        subgraph Pipeline_Box["📊 Pipeline Data"]
            FILT["filtered_places: SQL-filtered candidates"]
            MATCH["matched_interest_subcats: set[str]\n(semantic LLM match)"]
            CAND["candidate_places: ranked + diversity-optimized"]
            DRAFT["draft_itinerary: LLM-generated plan"]
            OPT["optimized_itinerary: route-optimized plan\n(+ accommodation_suggestions)"]
        end

        subgraph Validation_Box["✅ Validation"]
            VAL["validation: {score, issue, suggestion, metrics}"]
            IS_VAL["is_valid: bool"]
            ATT["planning_attempts: int"]
        end

        subgraph Control_Box["🎮 Control Flow"]
            ERR["error: str"]
            INTENT["intent_type: plan_trip / clarification / chat"]
            MISSING["missing_fields: [...]"]
            NEXT["next_agent: str"]
        end

        subgraph Meta_Box["🔍 Meta / Debug"]
            AGENT_MSGS["agent_messages: [trace logs]"]
            PROGRESS["progress_queue_key: Flutter push updates"]
        end
    end

    subgraph Agents["🤖 Pipeline Agents"]
        direction TB

        A1["1. Profile Loader\n───\n→ token, trip_id\n← profile"]
        A2["2. Place Retriever\n───\n→ destination_city, profile\n← filtered_places, matched_interest_subcats\n← agent_messages"]
        A3["3. Candidate Scorer\n───\n→ filtered_places, profile, duration_days\n→ matched_interest_subcats\n← candidate_places, agent_messages"]
        A4["4. Planning Agent\n───\n→ candidate_places, profile, destination_city\n→ duration_days, user_message\n→ validation (retry feedback)\n← draft_itinerary, planning_attempts\n← agent_messages"]
        A5["5. Route Optimizer\n───\n→ draft_itinerary\n← optimized_itinerary, agent_messages"]
        A7["6. Itinerary Validator\n───\n→ optimized_itinerary, user_message, profile\n← is_valid, validation, agent_messages"]
        A6["7. Hotel Selector\n(post-approval)\n───\n→ optimized_itinerary, candidate_places, profile\n← accommodation_suggestions, agent_messages"]
    end

    subgraph Edges["🔁 LangGraph Edges (Routing)"]
        E1["should_rank\nfiltered_places exists → scorer\nempty → end"]
        E2["should_plan\ncandidate_places exists → planner\nempty → end"]
        E3["should_optimize → optimizer"]
        E4["should_validate → validator"]
        E5["should_retry_or_end\nis_valid → end\nretries left → planner\nexhausted → end"]
    end

    subgraph External["🌐 External Services"]
        ES1["(Mock/Firebase) Profile DB"]
        ES2["PostgreSQL Places DB"]
        ES3["(Mock) OSRM Routing"]
        ES4["LLM (OpenAI/Groq/Claude)"]
    end

    %% ── Data flow: Profile → State ──────────────────────────────────
    TripProfile -.-o PROF

    %% ── Data flow: Agents → State ────────────────────────────────────
    A1 -- "writes profile" ----> PROF
    A2 -- "writes filtered_places" --> FILT
    A2 -- "writes matched_interest_subcats" --> MATCH
    A2 -- "writes agent_messages" -.-> AGENT_MSGS
    A3 -- "reads filtered_places" ----> FILT
    A3 -- "reads matched_interest_subcats" ----> MATCH
    A3 -- "reads duration_days" ----> DUR
    A3 -- "writes candidate_places" --> CAND
    A4 -- "reads candidate_places" ----> CAND
    A4 -- "reads destination_city" ----> DEST
    A4 -- "reads duration_days" ----> DUR
    A4 -- "reads user_message" ----> MSG
    A4 -- "reads validation (retry)" ----> VAL
    A4 -- "writes draft_itinerary" --> DRAFT
    A4 -- "writes planning_attempts" --> ATT
    A5 -- "reads draft_itinerary" ----> DRAFT
    A5 -- "writes optimized_itinerary" --> OPT
    A7 -- "reads optimized_itinerary" ----> OPT
    A7 -- "reads user_message" ----> MSG
    A7 -- "writes is_valid" --> IS_VAL
    A7 -- "writes validation" --> VAL
    A6 -- "reads optimized_itinerary" ----> OPT
    A6 -- "reads candidate_places" ----> CAND
    A6 -- "writes accommodation_suggestions" --> OPT

    PROF --> A1
    A1 --> A2
    ES2 --> A2
    A2 --> A3
    A3 --> A4
    ES4 --> A4
    A4 --> A5
    ES3 --> A5
    A5 --> A7
    ES4 --> A7
    A7 -. retry .-> A4
    A5 --> A6
    ES4 --> A6

    %% ── Edge routing ─────────────────────────────────────────────────
    A2 -.-> E1
    E1 -.->|filtered_places| A3
    E1 -.->|empty| END["⛔ End"]
    A3 -.-> E2
    E2 -.->|candidate_places| A4
    E2 -.->|none| END
    A4 -.-> E3
    E3 -.-> A5
    A5 -.-> E4
    E4 -.-> A7
    A7 -.-> E5
    E5 -.->|is_valid| END
    E5 -.->|retries left| A4
    E5 -.->|exhausted| END
    A1 -.-> ES1

    style END fill:#f96,stroke:#333,color:#000
    style TripState fill:#e1f5fe,stroke:#01579b
    style TripProfile fill:#f3e5f5,stroke:#7b1fa2
    style Agents fill:#e8f5e9,stroke:#2e7d32
```
