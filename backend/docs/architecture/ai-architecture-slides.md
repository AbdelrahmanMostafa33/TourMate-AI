# 🧠 TourMate AI — AI Architecture Slides

> Copy each slide's Mermaid diagram into **[Mermaid Live Editor](https://mermaid.live/)** → export as PNG/SVG → insert into your presentation.

---

## Slide 1: Title Slide — AI Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
graph TB
    subgraph Title["🧠 TourMate AI — AI Architecture"]
        direction TB
        T1["Multi-Agent Orchestration<br/>LangGraph State Machine"]
        T2["Dual-LLM Strategy<br/>Gemini + Groq"]
        T3["6-Node Planning Pipeline<br/>Profile → Validation"]
        T4["Conversation-Driven<br/>Slot Filling → Routing"]
    end

    Title --> T1
    Title --> T2
    Title --> T3
    Title --> T4

    style Title fill:#1a1a2e,color:#fff,stroke:#e94560,stroke-width:3px
    style T1 fill:#16213e,color:#e0e0e0,stroke:#e94560
    style T2 fill:#16213e,color:#e0e0e0,stroke:#e94560
    style T3 fill:#16213e,color:#e0e0e0,stroke:#e94560
    style T4 fill:#16213e,color:#e0e0e0,stroke:#e94560
```

---

## Slide 2: Dual-LLM Strategy

**Core concept:** Not one LLM — two providers, four agent groups, each matched to the right model for cost-efficiency and reliability.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
graph TB
    subgraph LLM["🧠 Dual-LLM Strategy"]
        direction TB
        
        GEMINI["<b>Google Gemini 2.5 Flash</b><br/>20 requests/day (free)"] --> G1
        GEMINI --> G2
        GEMINI --> G3
        
        G1["🧭 Planner<br/>Itinerary generation<br/>temperature=0.7"]
        G2["✏️ Modifier<br/>Surgical edits<br/>temperature=0.0"]
        G3["👁️ Vision<br/>Image analysis<br/>temperature=0.7"]

        GROQ["<b>Groq Llama 3.3 70B</b><br/>6,000+ requests/day (free)"] --> GR1
        GROQ --> GR2
        GROQ --> GR3
        GROQ --> GR4
        
        GR1["🔀 Router<br/>Message classification<br/>temperature=0.2"]
        GR2["⭐ Preference Reranker<br/>Vibe adjustments<br/>temperature=0.2"]
        GR3["✅ Validator<br/>Quality checks<br/>temperature=0.2"]
        GR4["🏨 Hotel Selector<br/>Accommodation picks<br/>temperature=0.3"]
    end

    style GEMINI fill:#4285F4,color:#fff,stroke:#fff
    style GROQ fill:#f55036,color:#fff,stroke:#fff
    
    style G1 fill:#16213e,color:#e0e0e0,stroke:#4285F4
    style G2 fill:#16213e,color:#e0e0e0,stroke:#4285F4
    style G3 fill:#16213e,color:#e0e0e0,stroke:#4285F4
    
    style GR1 fill:#16213e,color:#e0e0e0,stroke:#f55036
    style GR2 fill:#16213e,color:#e0e0e0,stroke:#f55036
    style GR3 fill:#16213e,color:#e0e0e0,stroke:#f55036
    style GR4 fill:#16213e,color:#e0e0e0,stroke:#f55036
```

### Key Design Decision

| Why split? | Gemini | Groq |
|---|---|---|
| **Rate limits** | 20 RPD (strict) | 6,000+ RPD (generous) |
| **Cost** | Free-tier capped | Free-tier massive |
| **Best at** | Planning, reasoning, multimodal | Classification, extraction, validation |
| **Agent roles** | Planner, Modifier, Vision | Router, Reranker, Validator, Hotel, Extractor |

**Pattern:** Use Gemini only for complex generation tasks that need its reasoning + multimodal capabilities. Route everything else to Groq (classify, extract, validate, rerank) — 300x more requests per day, same quality for those tasks.

---

## Slide 3: Multi-Agent Orchestration (LangGraph State Machine)

**Core concept:** Instead of one monolithic AI, specialized agents coordinated by a **state machine graph** — each agent handles one responsibility.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
graph TB
    subgraph Orchestrator["🎭 Orchestrator Layer"]
        direction TB
        
        MI["📨 Message Interpreter<br/>(Groq Router)
        Single LLM call → classifies:<br/>
        plan_trip | clarify | modify |
        approve | search_flights |
        select_hotel | answer_question"]

        MI -->|plan_trip| ACTION_PLAN
        MI -->|ask_clarification| ACTION_CLARIFY
        MI -->|modify_itinerary| ACTION_MODIFY
        MI -->|approve_itinerary| ACTION_APPROVE
        MI -->|search_flights| ACTION_FLIGHTS
        MI -->|select_hotel| ACTION_HOTEL
        
        ACTION_PLAN["🚀 Plan Trip"]
        ACTION_CLARIFY["💬 Ask Clarification"]
        ACTION_MODIFY["✏️ Modify Itinerary"]
        ACTION_APPROVE["✅ Approve & Next Phase"]
        ACTION_FLIGHTS["✈️ Search/Select Flights"]
        ACTION_HOTEL["🏨 Select Hotel"]
        
        ACTION_PLAN -->|Slots complete| PIPELINE["6-Node LangGraph Pipeline"]
        ACTION_PLAN -->|Missing info| CLARIFY["→ Slot Filling"]
        
        PIPELINE -->|Itinerary ready| ITINERARY["🗺️ Itinerary Presented"]
        ITINERARY -->|User modifies| ACTION_MODIFY
    end

    style MI fill:#0f3460,color:#fff,stroke:#e94560,stroke-width:2px
    style ACTION_PLAN fill:#16213e,color:#e0e0e0,stroke:#e94560
    style ACTION_CLARIFY fill:#16213e,color:#e0e0e0,stroke:#e94560
    style ACTION_MODIFY fill:#16213e,color:#e0e0e0,stroke:#e94560
    style ACTION_APPROVE fill:#16213e,color:#e0e0e0,stroke:#e94560
    style ACTION_FLIGHTS fill:#16213e,color:#e0e0e0,stroke:#e94560
    style ACTION_HOTEL fill:#16213e,color:#e0e0e0,stroke:#e94560
    style PIPELINE fill:#1a1a2e,color:#fff,stroke:#e94560,stroke-width:2px
    style CLARIFY fill:#16213e,color:#e0e0e0,stroke:#e94560
    style ITINERARY fill:#16213e,color:#e0e0e0,stroke:#e94560
```

### How it works:

1. **User sends message** → orchestrator reads conversation state from Redis
2. **Message Interpreter** (single Groq call) classifies the intent
3. **Router** dispatches to the correct handler:
   - `plan_trip` → check if slots complete → trigger 6-node pipeline
   - `modify_itinerary` → edit classifier → surgical edit | rerank | full regen
   - `approve_itinerary` → advance to next phase (flights → hotels → booking)
   - `search_flights` → Amadeus API call → format options
   - `select_hotel` → match user choice → transition to booking
4. **Conversation phase** is tracked as a state machine:
   `GREETING → SLOT_FILLING → PLAN_GENERATION → ITINERARY_REVIEW → FLIGHT_SELECTION → HOTEL_SELECTION → BOOKING → COMPLETED`

---

## Slide 4: Conversation Phase State Machine

**Core concept:** 8 distinct phases control what actions are allowed — preventing the user from booking a flight before the itinerary exists, or modifying a trip that's already finalized.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
stateDiagram-v2
    [*] --> GREETING
    GREETING --> SLOT_FILLING: User messages
    
    SLOT_FILLING --> PLAN_GENERATION: All slots collected
    
    PLAN_GENERATION --> ITINERARY_REVIEW: Pipeline complete
    
    ITINERARY_REVIEW --> ITINERARY_REVIEW: User modifies itinerary
    
    ITINERARY_REVIEW --> FLIGHT_SELECTION: User approves
    
    FLIGHT_SELECTION --> HOTEL_SELECTION: Flight selected or skipped
    
    HOTEL_SELECTION --> BOOKING: Hotel selected
    
    BOOKING --> COMPLETED: Pay now / later
    
    COMPLETED --> [*]: Terminal state
    
    note right of PLAN_GENERATION
        LangGraph 6-node pipeline
        User sees progress events
        Timeout: 10 minutes
    end note
    
    note right of COMPLETED
        One conversation = one trip
        Only "answer_question"
        allowed in this phase
    end note
```

### Safety Overrides (RLHF-style)

The orchestrator overrides the message interpreter when it misclassifies:

| Scenario | Override |
|---|---|
| `ask_clarification` but slots are complete | Force `plan_trip` |
| In `HOTEL_SELECTION` but action ≠ `select_hotel` | Check for hotel keywords → override |
| In `BOOKING` but action ≠ `approve_itinerary` | Check for "pay"/"later" keywords → override |
| `plan_trip` but interests are empty | Force back to `ask_clarification` |

---

## Slide 5: 6-Node LangGraph Pipeline (Itinerary Generation)

**Core concept:** The heart of the AI — a directed graph where each node is a specialized agent. Conditional edges control flow based on outputs.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
graph LR
    subgraph Pipeline["⚡ 6-Node LangGraph Pipeline"]
        direction LR
        
        ENTRY(["Entry"]) --> LOAD["1️⃣ Load Profile<br/>(DB or Mock)"]
        
        LOAD --> RETRIEVAL["2️⃣ Place Retrieval<br/>(SQL-style filtering)"]
        
        RETRIEVAL -->|has places| RANK["3️⃣ Candidate Scoring<br/>(Multi-signal + diversity)"]
        RETRIEVAL -->|no places| END1([END])
        
        RANK -->|has candidates| PLAN["4️⃣ Planning Agent<br/>(Gemini generates itinerary)"]
        RANK -->|no candidates| END2([END])
        
        PLAN --> OPT["5️⃣ Route Optimizer<br/>(OSRM + 2-opt)"]
        
        OPT --> VAL["6️⃣ Itinerary Validator<br/>(Score + LLM quality check)"]
        
        VAL -->|valid ✅| END3([✅ END])
        VAL -->|invalid ⚠️| RETRY{"Retry left?"}
        RETRY -->|Yes| PLAN
        RETRY -->|No| END3
        
        LOAD -.->|Progress| UI["📱 Flutter UI"]
        RETRIEVAL -.->|Progress| UI
        RANK -.->|Progress| UI
        PLAN -.->|Progress| UI
        OPT -.->|Progress| UI
        VAL -.->|Progress| UI
    end

    style LOAD fill:#0f3460,color:#fff,stroke:#e94560
    style RETRIEVAL fill:#16213e,color:#e0e0e0,stroke:#e94560
    style RANK fill:#16213e,color:#e0e0e0,stroke:#e94560
    style PLAN fill:#4285F4,color:#fff,stroke:#fff
    style OPT fill:#16213e,color:#e0e0e0,stroke:#e94560
    style VAL fill:#16213e,color:#e0e0e0,stroke:#e94560
    style RETRY fill:#1a1a2e,color:#fff,stroke:#e94560,stroke-width:2px
    style UI fill:#333,color:#fff,stroke:#666
```

### Node Details

| Node | Model | What it does |
|---|---|---|
| **1. Load Profile** | — | Load per-trip profile from DB; fallback to mock if no auth token |
| **2. Place Retrieval** | — | SQL-style DB filtering by city, category, sub_category, budget |
| **3. Candidate Scoring** | — | Multi-signal formula (embedding similarity + rating + review count) + diversity enforcement |
| **4. Planning Agent** | **Gemini** | Generates themed day-by-day itinerary from top candidates |
| **5. Route Optimizer** | OSRM API | Reorders stops by travel time using OSRM + 2-opt heuristic |
| **6. Itinerary Validator** | **Groq** | Programmatic checks + LLM quality score → retry from planner (max 2x) |

---

## Slide 6: Agent: Message Interpreter (Dual-Intent Router)

**Core concept:** A single Groq Llama 70B call replaces the old 3-call pattern — it sees full conversation history, current phase, and past preferences.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
flowchart TB
    subgraph Interpreter["📨 Message Interpreter"]
        direction TB
        
        INPUT["User Message +<br/>Conversation History (last 10)<br/>+ Current Phase + Slots"]
        
        INPUT --> LLM["Groq Llama 3.3 70B<br/>temperature=0.2"]
        
        LLM --> OUTPUT["Structured Output"]
        
        OUTPUT --> ACTION{"Action"}
        
        ACTION -->|plan_trip| P1["→ Check slots complete?"]
        ACTION -->|ask_clarification| P2["→ Ask follow-up question"]
        ACTION -->|answer_question| P3["→ General chat response"]
        ACTION -->|modify_itinerary| P4["→ Route to Edit Classifier"]
        ACTION -->|approve_itinerary| P5["→ Advance to next phase"]
        ACTION -->|search_flights| P6["→ Route to Flight Selection"]
        ACTION -->|select_flight| P7["→ Match user choice"]
        ACTION -->|select_hotel| P8["→ Match hotel choice"]
        
        P1 -->|Yes| PLAN_GEN["Trigger Pipeline"]
        P1 -->|No| SLOT_FILL["Ask for missing fields"]
        
        P2 --> RESP["Natural response"]
        
        subgraph SLOTS["Extracted Slot Data"]
            S1["destination_city"]
            S2["duration_days"]
            S3["interests"]
            S4["budget_level"]
            S5["travel_style"]
            S6["origin_city"]
            S7["travel_dates"]
            S8["group_size"]
        end
        
        LLM -.-> SLOTS
    end

    style INPUT fill:#16213e,color:#e0e0e0,stroke:#f55036
    style LLM fill:#f55036,color:#fff,stroke:#fff,stroke-width:2px
    style OUTPUT fill:#0f3460,color:#fff,stroke:#e94560
    style RESP fill:#16213e,color:#e0e0e0,stroke:#e94560
    style PLAN_GEN fill:#4285F4,color:#fff,stroke:#fff
    style SLOT_FILL fill:#16213e,color:#e0e0e0,stroke:#e94560
```

### Hallucination Guard

The orchestrator detects when the LLM invents interests the user never mentioned:

```python
# Check: did the user actually mention these interests?
extracted_interests = router_result.extracted.get("interests")
if extracted_interests and effective_message:
    user_mentioned = any(
        interest.lower() in effective_message.lower()
        for interest in extracted_interests
    )
    if not user_mentioned:
        # Clear hallucinated interests back to None
        state.slots.interests = None
```

---

## Slide 7: Agent: Planning Agent (Itinerary Generator)

**Core concept:** Gemini generates a structured, day-by-day itinerary from a pool of candidate places. If validation fails, the prompt is rebuilt with feedback and retried.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
flowchart TB
    subgraph Planner["🧭 Planning Agent (Gemini)"]
        direction TB
        
        IN["Input: Profile + Top 20-30<br/>Candidate Places + Preferences"]
        
        IN --> BUILD["Build System Prompt<br/>
        - Agent role: Expert travel planner
        - Day count constraint
        - Stops per day limit
        - Category diversity requirement"]
        
        BUILD --> GEN["Generate Itinerary<br/>Gemini 2.5 Flash<br/>temperature=0.7"]
        
        GEN --> SCHEMA["Structured Output<br/>Pydantic: TripItinerary"]
        
        SCHEMA --> CHECK{"Validation OK?"}
        
        CHECK -->|Yes| OUTPUT["✅ Draft Itinerary<br/>{
          destination, days: [
            {day_number, theme, stops: [
              {place_id, name, time_of_day,
               duration_minutes, why_recommended}
            ]}
          ]
        }"]
        
        CHECK -->|No - Validation Error| RETRY{"Retry <br/>Max 2?"}
        RETRY -->|Yes| REBUILD["Rebuild prompt with<br/>validation error feedback"]
        RETRY -->|No| ERROR["Return error state"]
        REBUILD --> GEN
    end

    style IN fill:#16213e,color:#e0e0e0,stroke:#4285F4
    style BUILD fill:#16213e,color:#e0e0e0,stroke:#4285F4
    style GEN fill:#4285F4,color:#fff,stroke:#fff,stroke-width:2px
    style SCHEMA fill:#0f3460,color:#fff,stroke:#e94560
    style OUTPUT fill:#1a1a2e,color:#fff,stroke:#e94560,stroke-width:2px
    style REBUILD fill:#16213e,color:#e0e0e0,stroke:#e94560
    style ERROR fill:#333,color:#e0e0e0,stroke:#e94560
```

---

## Slide 8: Agent: Edit Classifier (Modify Intent Router)

**Core concept:** When a user wants to change the itinerary, a fast Groq call classifies the edit type → routes to the right handler.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
flowchart TB
    subgraph Classifier["✏️ Edit Classifier (Groq)"]
        direction TB
        
        USER_MSG["User says:<br/>'Swap day 2 with day 4'<br/>'Make this day more relaxed'<br/>'Add a museum here'<br/>'I want it packed'"]
        
        USER_MSG --> CLASSIFY["Groq Llama 3.3 70B<br/>temperature=0.1<br/>
        Classify + Extract:
        - edit_type
        - target_day
        - entity_names
        - reasoning"]
        
        CLASSIFY --> ROUTE{"Edit Type"}
        
        ROUTE -->|PREFERENCE| PREF["💫 Preference Edit<br/>→ Reranker Agent"]
        ROUTE -->|SURGICAL| SURG["🔧 Surgical Edit<br/>→ Modifier Agent"]
        ROUTE -->|REGENERATE| REGEN["🔄 Full Regeneration<br/>→ Full Pipeline"]
        ROUTE -->|ADD_PLACE| SURG2["→ Modifier Agent<br/>(with pool enrichment)"]
        ROUTE -->|SWAP| SURG3["→ Modifier Agent"]
        ROUTE -->|REMOVE| SURG4["→ Modifier Agent"]
        
        PREF --> FALLBACK{"Reranker<br/>succeeds?"}
        FALLBACK -->|Yes| DONE["✅ Rerank & Replan"]
        FALLBACK -->|No| FALL_SURG["→ Try Modifier Agent"]
        FALL_SURG --> FALL_REG["→ Full Pipeline<br/>Regeneration"]
        
        SURG2 --> SURG_OK{"Modifier<br/>succeeds?"}
        SURG_OK -->|Yes| OPT["Post-edit: Route Optimizer<br/>+ Slot Rebalancing"]
        SURG_OK -->|No| REGEN
    end

    style USER_MSG fill:#16213e,color:#e0e0e0,stroke:#f55036
    style CLASSIFY fill:#f55036,color:#fff,stroke:#fff,stroke-width:2px
    style PREF fill:#0f3460,color:#fff,stroke:#e94560
    style SURG fill:#0f3460,color:#fff,stroke:#e94560
    style SURG2 fill:#0f3460,color:#fff,stroke:#e94560
    style SURG3 fill:#0f3460,color:#fff,stroke:#e94560
    style SURG4 fill:#0f3460,color:#fff,stroke:#e94560
    style REGEN fill:#4285F4,color:#fff,stroke:#fff
    style OPT fill:#16213e,color:#e0e0e0,stroke:#e94560
    style DONE fill:#1a1a2e,color:#fff,stroke:#e94560
```

### Fallback Chain

```
User Edit Request
    │
    ├─ Preference Adjustment (Reranker Agent)
    │   │
    │   ├─ Success → Re-rank candidates → Re-plan
    │   │
    │   └─ Failure → Try Modifier Agent
    │                 │
    │                 ├─ Success → Post-edit optimization
    │                 │
    │                 └─ Failure → Full Pipeline Regeneration
    │
    ├─ Surgical Edit (Modifier Agent - delta-based)
    │   │
    │   ├─ Success → Post-edit optimization
    │   │
    │   └─ Failure → Full Pipeline Regeneration
    │
    └─ Full Regeneration
```

---

## Slide 9: Agent: Itinerary Modifier (Surgical Delta Edits)

**Core concept:** Instead of regenerating the entire itinerary, the modifier outputs **delta operations** (REMOVE, SWAP, ADD, REORDER) — cheaper, faster, and preserves unchanged content.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
flowchart TB
    subgraph Modifier["✏️ Itinerary Modifier Agent (Gemini)"]
        direction TB
        
        IN["Input:
        - Current itinerary (full JSON)
        - Modification request (user text)
        - Available places pool
        - User preferences
        
        temperature=0.0 (deterministic)"]
        
        IN --> SEARCH["Hybrid Search for New Places
        - Category matching from request
        - Semantic similarity
        - Top-N from pool"]
        
        SEARCH --> LLM["Gemini 2.5 Flash
        temperature=0.0
        
        Output: Delta Operations"]
        
        LLM --> OPS{"Operations"}
        
        subgraph DELTA["Delta Operations"]
            OP1["REMOVE place_id"]
            OP2["SWAP day_A ↔ day_B"]
            OP3["ADD {place_id, day, time, duration}"]
            OP4["REORDER stops within day"]
            OP5["RE_THEME {day, new_theme}"]
        end
        
        LLM -.-> DELTA
        
        OPS --> APPLY["Apply Deltas to Itinerary"]
        APPLY --> CHECK{"Real modifications<br/>detected?"}
        
        CHECK -->|Yes| OPTIMIZE["Post-Edit:
        1. Rebalance clustered slots
        2. OSRM re-optimize affected days
        3. Validate"]
        CHECK -->|No| FAIL["Return unchanged + modifier_note"]
        
        OPTIMIZE --> DONE["✅ Modified Itinerary"]
    end

    style IN fill:#16213e,color:#e0e0e0,stroke:#4285F4
    style SEARCH fill:#16213e,color:#e0e0e0,stroke:#4285F4
    style LLM fill:#4285F4,color:#fff,stroke:#fff,stroke-width:2px
    style APPLY fill:#0f3460,color:#fff,stroke:#e94560
    style OPTIMIZE fill:#0f3460,color:#fff,stroke:#e94560
    style DONE fill:#1a1a2e,color:#fff,stroke:#e94560,stroke-width:2px
    style FAIL fill:#333,color:#e0e0e0,stroke:#e94560
```

---

## Slide 10: LLM Invocation Layer (Resilience & Fallback)

**Core concept:** Every LLM call goes through `invoke_with_fallback()` — a robust retry layer that handles rate limits, transient errors, schema failures, and key rotation automatically.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
flowchart TB
    subgraph Invoke["⚙️ invoke_with_fallback()"]
        direction TB
        
        CALL["Call for agent_role
        e.g. 'planner', 'router'"] --> GET_KEY["KeyManager.get_key(provider)
        Round-robin key selection"]
        
        GET_KEY --> BUILD_LLM["Build LLM instance
        ChatGoogleGenerativeAI / ChatGroq
        
        max_retries=0
        (handled externally)"]
        
        BUILD_LLM --> ATTEMPT["Attempt LLM call
        with_structured_output?"]
        
        ATTEMPT --> RESULT{"Result"}
        
        RESULT -->|200 OK| RETURN["✅ Return response"]
        RESULT -->|429 Rate Limit| RETRY_KEY["Mark key as exhausted
        Try next key"]
        RESULT -->|503 Transient| BACKOFF["Exponential backoff
        1s → 2s → 4s → 5s max"]
        RESULT -->|413 Too Large| RAISE["🚨 Raise immediately
        (cycling keys won't help)"]
        RESULT -->|400 Schema Error| SCHEMA_RETRY["Retry with same key
        Max 2 attempts
        (LLM non-determinism)"]
        RESULT -->|Other Error| RAISE2["🚨 Raise immediately"]
        
        RETRY_KEY --> GET_KEY
        BACKOFF --> GET_KEY
        SCHEMA_RETRY --> ATTEMPT
        
        RETRY_KEY -->|All keys exhausted| EXHAUSTED{"All keys tried?"}
        EXHAUSTED -->|Transient errors| BACKOFF2["Wait + full retry cycle"]
        EXHAUSTED -->|Non-transient| RAISE3["🚨 Raise last error"]
        BACKOFF2 --> GET_KEY
    end

    style CALL fill:#16213e,color:#e0e0e0,stroke:#f55036
    style GET_KEY fill:#16213e,color:#e0e0e0,stroke:#f55036
    style BUILD_LLM fill:#16213e,color:#e0e0e0,stroke:#f55036
    style ATTEMPT fill:#0f3460,color:#fff,stroke:#e94560
    style RETURN fill:#1a1a2e,color:#fff,stroke:#00ff00,stroke-width:2px
    style RAISE fill:#333,color:#e0e0e0,stroke:#ff0000
    style RAISE2 fill:#333,color:#e0e0e0,stroke:#ff0000
    style RAISE3 fill:#333,color:#e0e0e0,stroke:#ff0000
```

### Error Classification

| HTTP/Error | Classification | Action |
|---|---|---|
| **429** Rate Limit | `_is_rate_limit_error()` | Try next API key immediately |
| **403** Permission Denied (Gemini) | Caught by same function | Treated as rate limit — try next key |
| **503** Service Unavailable | `_is_transient_error()` | Exponential backoff (1s → 2s → 4s → 5s), then retry |
| **413** Request Too Large | `_is_request_too_large_error()` | Raise immediately — no key will fix this |
| **400** Schema Validation | `_is_schema_validation_error()` | Retry same key up to 2x (LLM non-determinism resolves it) |
| Any other | — | Raise immediately |

---

## Slide 11: AI Architecture Layers — Complete Stack

**Everything together:** the full AI Engine from top to bottom.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'primaryTextColor': '#fff', 'secondaryTextColor': '#e0e0e0', 'lineColor': '#e94560'}}}%%
graph TB
    subgraph FULL["🧠 AI Engine — Full Architecture"]
        direction TB
        
        L1["📲 Interface Layer"] --> L1_1["REST API Endpoint: POST /api/v1/chat"]
        L1 --> L1_2["WebSocket: /api/v1/chat/stream"]
        L1 --> L1_3["Image Upload: /api/v1/images/analyze"]
        
        L1_1 --> ORCH
        L1_2 --> ORCH
        L1_3 --> VISION["Vision Pipeline:
        Gemini Image Analysis
        → Multimodal Fusion
        → Profile Update"]
        
        VISION -->|Fused interests| ORCH
        
        L2["🎭 Orchestration Layer"] --> ORCH["Orchestrator:
        Phase State Machine
        Message Routing
        Redis Session Management
        
        ConversationPhase:
        GREETING → SLOT_FILLING → PLAN_GENERATION
        → ITINERARY_REVIEW → FLIGHT_SELECTION
        → HOTEL_SELECTION → BOOKING → COMPLETED"]
        
        ORCH --> INT["Message Interpreter (Groq)
        Single-call: action + slot extraction"]
        
        INT --> PIPELINE
        
        L3["⚡ Pipeline Layer"] --> PIPELINE["LangGraph State Graph
        6 Nodes:
        LoadProfile → Retrieval → Scoring
        → Planning (Gemini) → Optimization (OSRM)
        → Validation (Groq)"]
        
        PIPELINE --> AGENTS
        
        L4["🤖 Agent Layer"] --> AGENTS["6 Specialized Agents:
        
        🧭 Planning Gemini (0.7)
        ✏️ Modifier Gemini (0.0)
        🔀 Router Groq (0.2)
        ⭐ Reranker Groq (0.2)
        ✅ Validator Groq (0.2)
        🏨 Hotel Selector Groq (0.3)"]
        
        AGENTS --> RESILIENCE
        
        L5["🔁 Resilience Layer"] --> RESILIENCE["invoke_with_fallback():
        
        Multi-Key Rotation
        Rate Limit (429) → Next Key
        Transient (503) → Backoff → Retry
        Schema Error (400) → Retry × 2
        Too Large (413) → Raise
        
        2 Providers × N keys each
        Gemini: 20 RPD total
        Groq: 6,000+ RPD total"]
        
        RESILIENCE --> DATA
        
        L6["💾 Data Layer"] --> DATA["PostgreSQL (places, profiles, trips)
        Redis (session state, progress queues)
        Embeddings (semantic place search)"]
        
        L7["🔗 External APIs"] --> EXT["Google Gemini API
        Groq API (Llama 3.3 70B)
        Google Embeddings
        OSRM Routing
        Amadeus Flights
        Firebase Auth"]
        
        DATA --> EXT
    end

    style L1 fill:#16213e,color:#e0e0e0,stroke:#e94560
    style L2 fill:#0f3460,color:#fff,stroke:#e94560
    style L3 fill:#1a1a2e,color:#fff,stroke:#e94560,stroke-width:2px
    style L4 fill:#0f3460,color:#fff,stroke:#e94560
    style L5 fill:#16213e,color:#e0e0e0,stroke:#e94560
    style L6 fill:#16213e,color:#e0e0e0,stroke:#e94560
    style L7 fill:#16213e,color:#e0e0e0,stroke:#e94560
    
    style ORCH fill:#1a1a2e,color:#fff,stroke:#e94560,stroke-width:2px
    style INT fill:#f55036,color:#fff,stroke:#fff
    style PIPELINE fill:#4285F4,color:#fff,stroke:#fff,stroke-width:2px
    style AGENTS fill:#0f3460,color:#fff,stroke:#e94560
    style RESILIENCE fill:#1a1a2e,color:#fff,stroke:#e94560,stroke-width:2px
    style VISION fill:#16213e,color:#e0e0e0,stroke:#4285F4
```

---

## Slide 12: Key Design Principles (Summary Slide)

### 6 Principles That Shaped the AI Architecture

| # | Principle | Implementation |
|---|---|---|
| 1 | **Single-Responsibility Agents** | Each agent handles exactly one task (plan, modify, classify, validate) — no monolithic prompts |
| 2 | **Dual-LLM Cost Optimization** | Gemini for complex generation (20 req/day), Groq for everything else (6,000+ req/day) |
| 3 | **Resilience by Design** | `invoke_with_fallback()`: multi-key rotation, exponential backoff, schema retry — every LLM call is protected |
| 4 | **Surgical Over Regeneration** | Edit classifier → modifier agent (delta ops) → reranker → full regen as last resort |
| 5 | **State Machine Guardrails** | 8 conversation phases prevent invalid actions; RLHF-style overrides fix misclassifications |
| 6 | **Hallucination Defense** | Interest guard clears LLM-invented preferences; safety checks at every transition |

---

## How to Use These Slides

1. **Copy each Mermaid code block** into [Mermaid Live Editor](https://mermaid.live/)
2. **Export as PNG/SVG** for your slides
3. **Insert into PowerPoint / Google Slides / Canva**
4. **Speaker notes** are included in the text below each diagram

### Presentation Ordering

| Slide | Topic | Time (min) |
|---|---|---|
| 1 | Title — AI Architecture overview | 0:30 |
| 2 | Dual-LLM Strategy — why two models | 1:30 |
| 3 | Multi-Agent Orchestration — the state machine | 1:30 |
| 4 | Conversation Phase State Machine — 8 phases | 1:00 |
| 5 | 6-Node LangGraph Pipeline — itinerary generation | 2:00 |
| 6 | Message Interpreter — single-call routing | 1:00 |
| 7 | Planning Agent — itinerary generation | 1:30 |
| 8 | Edit Classifier — modify intent routing | 1:00 |
| 9 | Itinerary Modifier — surgical delta edits | 1:00 |
| 10 | LLM Invocation Layer — resilience & fallback | 1:30 |
| 11 | Full Architecture Stack — all layers together | 1:00 |
| 12 | Key Design Principles — summary | 0:30 |
