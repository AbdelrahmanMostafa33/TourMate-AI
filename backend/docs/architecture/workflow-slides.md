# TourMate AI — Presentation Slides: User Workflow Flow Diagram

Copy each slide's content into your presentation tool (PowerPoint, Google Slides, Canva, etc.).

---

## 📽️ Slide 1 — Title Slide

**Title:** TourMate AI — Intelligent Travel Planning Workflow

**Subtitle:** From User Request to Personalized Trip Booking

**Bottom text:** Graduation Project — AI-Powered Travel Assistant

**Suggested Visual:** Place the TourMate AI logo centered, with a world map background silhouette, and the 6 main phase icons in a horizontal row at the bottom:
```
[💬 Chat] → [🧠 AI Plans] → [✈️ Flights] → [🏨 Hotels] → [💳 Booking] → [✅ Done]
```

---

## 📽️ Slide 2 — User Sends a Request

**Title:** Step 1 — User Sends a Request

**Visual:**

```mermaid
flowchart LR
    A["👤 User"] -->|"Types a message"| B["💬 Chat Interface<br/><i>Flutter App</i>"]
    A -->|"Uploads a photo"| C["📸 Image Upload<br/><i>Gemini Vision</i>"]
    B --> D["📡 WebSocket / REST API<br/><i>FastAPI Backend</i>"]
    C --> D
    D --> E["🧠 Orchestrator<br/><i>process_message()</i>"]
    
    style A fill:#6c63ff,color:#fff
    style B fill:#16213e,color:#fff
    style C fill:#16213e,color:#fff
    style D fill:#0f3460,color:#fff
    style E fill:#e94560,color:#fff
```

**Key Points:**
- User types a natural language message (e.g., "Plan a 5-day trip to Cairo")
- OR uploads a travel photo for visual analysis
- Message sent via WebSocket for real-time streaming
- REST API for CRUD operations

**Example User Input:** `"Plan a romantic 5-day trip to Cairo with a moderate budget"`

---

## 📽️ Slide 3 — Message Interpretation

**Title:** Step 2 — AI Interprets the Message

**Visual:**

```mermaid
flowchart TB
    subgraph Input["Input"]
        A["📨 User Message"]
    end
    subgraph Interpreter["Message Interpreter"]
        B["🧠 Gemini LLM<br/><i>Single structured call</i>"]
    end
    subgraph Output["Structured Output"]
        C1["🎯 Action:<br/>plan_trip / ask_clarification"]
        C2["📋 Extracted Slots:<br/>City, Duration, Interests..."]
        C3["💬 Natural Response:<br/>Conversational reply"]
    end
    Input --> Interpreter
    Interpreter --> Output
    
    style Input fill:#16213e,color:#fff
    style Interpreter fill:#e94560,color:#fff
    style Output fill:#0f3460,color:#fff
    style B fill:#e94560,color:#fff
```

**How It Works:**
- A single LLM call replaces the old 3-call pattern (intent parser + clarification + chat)
- The LLM sees the full conversation history (last 10 messages)
- Outputs structured JSON with guaranteed schema via Pydantic
- **Safety Overrides** catch misclassifications (e.g., hotel keywords → `select_hotel`)

**Extracted Example:**
```
Action: plan_trip
City: Cairo | Duration: 5 days | Interests: [romantic, history, food]
Budget: moderate | Style: romantic | Pace: relaxed
```

---

## 📽️ Slide 4 — Slot Filling (Data Collection)

**Title:** Step 3 — Conversational Data Collection

**Visual:**

```mermaid
flowchart LR
    A["🗺️ Destination City"] -->|"Cairo"| E
    B["📅 Duration"] -->|"5 days"| E
    C["🎯 Interests"] -->|"history, food, romantic"| E
    D["📎 Other Slots:<br/>Budget, Style, Pace,<br/>Group Size, Dates..."] -->|"Defaults applied"| E
    
    E["✅ Slots Complete?"]
    E -->|"No — missing info"| F["🤔 Ask User<br/><i>One question at a time</i>"]
    E -->|"Yes — all collected"| G["🚀 Proceed to<br/>Plan Generation"]
    
    style A fill:#16213e,color:#fff
    style B fill:#16213e,color:#fff
    style C fill:#16213e,color:#fff
    style D fill:#16213e,color:#fff
    style E fill:#6c63ff,color:#fff
    style F fill:#0f3460,color:#fff
    style G fill:#00b894,color:#fff
```

**Process:**
- Collects: City, Duration, Interests, Budget, Travel Style, Pace, Dates, Group Size
- **Smart defaults** for budget, style, pace → never ask unless needed
- **Interest guard:** Before planning, verifies interests are genuinely provided (not LLM-hallucinated)
- **Safety:** If user gives a country name (e.g., "Egypt"), asks for a specific city
- **Image fusion:** If user uploaded a photo, detected interests are merged into the slots

**Example Conversation:**
```
User:  "Plan a trip to Cairo"
TourMate: "Great! How many days are you planning?"
User:  "5 days"
TourMate: "What are you interested in? History, food, museums...?"
```

---

## 📽️ Slide 5 — Profile Loading & Place Retrieval

**Title:** Step 4 — Loading Profile & Discovering Places

**Visual:**

```mermaid
flowchart LR
    subgraph LoadProfile["1. Load Profile"]
        A1["📂 Load per-trip profile<br/>from PostgreSQL"]
        A2["👤 Set preferences:<br/>budget, style, pace, interests"]
    end
    subgraph Retrieve["2. Place Retrieval"]
        B1["🔍 SQL Filter by City<br/>& Category"]
        B2["📊 Database Query<br/><i>places table</i>"]
        B3["📋 Returns filtered_places<br/><i>Cairo attractions</i>"]
    end
    subgraph Score["3. Candidate Scoring"]
        C1["⭐ Multi-signal scoring"]
        C2["🎯 Diversity optimization"]
        C3["📋 Top candidates → planner"]
    end
    
    LoadProfile --> Retrieve --> Score
    
    style LoadProfile fill:#16213e,color:#fff
    style Retrieve fill:#0f3460,color:#fff
    style Score fill:#16213e,color:#fff
```

**Key Details:**
- **Profile:** Per-trip profile loaded from DB (not a static user profile — allows budget-conscious for Istanbul but luxury for Thailand)
- **Retrieval:** SQL-style filtering by city and category
- **Scoring:** Multi-signal formula + diversity optimization to avoid recommending 5 museums in a row

---

## 📽️ Slide 6 — AI Itinerary Planning

**Title:** Step 5 — AI Generates the Itinerary

**Visual:**

```mermaid
flowchart TB
    subgraph Planner["Planning Agent (Gemini LLM)"]
        P1["📥 Receives top candidates<br/>+ user profile"]
        P2["🧠 Generates day-by-day<br/>themed itinerary"]
        P3["📝 Assigns time slots,<br/>durations, recommendations"]
    end
    
    subgraph Output["Output Structure"]
        O1["🗓️ Day 1 — Historical Cairo<br/>• Egyptian Museum (Morning)<br/>• Citadel (Afternoon)<br/>• Khan El Khalili (Evening)"]
        O2["🗓️ Day 2 — Coptic Cairo<br/>• Hanging Church (Morning)<br/>• ..."]
        O3["🗓️ Day 3 — Food & Culture<br/>• ..."]
    end
    
    Planner --> Output
    
    style Planner fill:#e94560,color:#fff
    style Output fill:#16213e,color:#fff
    style P1 fill:#e94560,color:#fff
    style P2 fill:#e94560,color:#fff
    style P3 fill:#e94560,color:#fff
```

**How the LLM Plans:**
- Consumes pre-ranked candidates from upstream scoring
- Organizes places into themed days (e.g., "Historical Cairo", "Food Tour")
- Assigns time-of-day slots (morning/afternoon/evening)
- Includes why-recommended explanations for each stop
- Handles rate limits with automatic retry + progress reporting

**Progress Reported to User:**
```
"Building your 5-day itinerary..." → "Created 5 days with 18 stops"
```

---

## 📽️ Slide 7 — Route Optimization

**Title:** Step 6 — Optimizing the Route

**Visual:**

```mermaid
flowchart LR
    A["🗺️ Draft Itinerary<br/><i>Unoptimized stops</i>"] --> B["🌐 OSRM API<br/><i>Open Source Routing</i>"]
    B --> C["📐 2-opt Reordering<br/><i>Minimize travel time</i>"]
    C --> D["📊 Rebalance<br/>Clustered Slots"]
    D --> E["✅ Optimized Itinerary<br/><i>Efficient day routes</i>"]
    
    style A fill:#16213e,color:#fff
    style B fill:#0f3460,color:#fff
    style C fill:#0f3460,color:#fff
    style D fill:#0f3460,color:#fff
    style E fill:#00b894,color:#fff
```

**Optimization Process:**
- **OSRM** calculates real driving/walking times between consecutive stops
- **2-opt algorithm** reorders stops to minimize total travel time per day
- **Slot rebalancing** clusters nearby places together
- Prevents zigzagging across the city

**Before vs After:**
```
Before: Museum → Far Park → Market → Another Far Museum
After:  Museum → Nearby Gallery → Market → Park (grouped by proximity)
```

---

## 📽️ Slide 8 — Itinerary Validation

**Title:** Step 7 — Quality Validation

**Visual:**

```mermaid
flowchart TB
    subgraph Validate["Itinerary Validator"]
        V1["🔍 Programmatic Checks<br/><i>Feasibility, timing,<br/>overlapping slots</i>"]
        V2["🧠 LLM Quality Review<br/><i>Scores itinerary /100</i>"]
    end
    
    Validate --> C{"Score ≥ threshold?"}
    C -->|"✅ Valid"| D["🎉 Pipeline Complete<br/>Phase → ITINERARY_REVIEW"]
    C -->|"❌ Invalid<br/>≤ 2 retries"| E["🔄 Retry from Planner<br/><i>Improved prompt</i>"]
    C -->|"❌ Invalid<br/>Retries exhausted"| F["✅ End Gracefully<br/><i>Keep last itinerary</i>"]
    
    style Validate fill:#16213e,color:#fff
    style C fill:#6c63ff,color:#fff
    style D fill:#00b894,color:#fff
    style E fill:#e94560,color:#fff
    style F fill:#0f3460,color:#fff
```

**Validation Checks:**
- **Programmatic:** Are time slots feasible? Are stops in logical order? Are any stops overlapping?
- **LLM Review:** Gemini scores the itinerary out of 100 based on quality, diversity, and feasibility
- **Retry Mechanism:** Up to 2 automatic retries from the planner node with improved prompts
- **Graceful Degradation:** If validation fails after max retries, the itinerary is still presented to the user

---

## 📽️ Slide 9 — Itinerary Review & Modification

**Title:** Step 8 — User Reviews & Modifies

**Visual:**

```mermaid
flowchart TB
    U["👤 User Views Itinerary"]
    U --> Choice{"User Action"}
    
    Choice -->|"✅ Approve"| A["➡️ Proceed to Flights"]
    Choice -->|"❓ Ask Question"| Q["💬 answer_question<br/><i>General chat</i>"]
    Choice -->|"✏️ Modify"| M["🧩 Edit Classifier"]
    
    subgraph EditTypes["Edit Classification"]
        E1["🔧 Surgical Edit<br/><i>add/remove one place</i>"]
        E2["🎨 Preference Edit<br/><i>change vibe/style</i>"]
        E3["🏨 Acc. Change<br/><i>resorts instead</i>"]
        E4["🔄 Regenerate<br/><i>major overhaul</i>"]
    end
    
    M --> EditTypes
    
    E1 -->|"Itinerary Modifier Agent"| R1["Post-edit Route Opt."]
    E2 -->|"Reranker + Replan"| R2["Updated Itinerary"]
    E3 -->|"Swap Hotels Surgically"| R3["Stops Preserved"]
    E4 -->|"Full Pipeline Re-run"| R4["New Itinerary"]
    
    R1 & R2 & R3 & R4 --> U
    
    style U fill:#6c63ff,color:#fff
    style Choice fill:#6c63ff,color:#fff
    style A fill:#00b894,color:#fff
    style Q fill:#0f3460,color:#fff
    style M fill:#e94560,color:#fff
    style EditTypes fill:#16213e,color:#fff
```

**Edit Classification Flow:**
1. **Accommodation change** (e.g., "resorts instead of hotels") → intercepted first, surgical swap
2. **Edit Classifier** determines the edit type:
   - **Surgical:** Modifier agent adds/removes/replaces a specific place → post-edit route optimization
   - **Preference:** Reranker re-ranks candidates → re-plans with new preferences
   - **Regenerate:** Full pipeline re-run from scratch
3. If the modifier fails, falls back to full regeneration

---

## 📽️ Slide 10 — Flight Selection

**Title:** Step 9 — Flight Selection (Amadeus)

**Visual:**

```mermaid
flowchart TB
    F["✈️ FLIGHT_SELECTION Phase"]
    F --> Q["Ask: Where are you flying from?"]
    Q --> S["User provides origin city"]
    S --> D["Auto-detect: round-trip?<br/>Compute return date from trip duration"]
    D --> C["Detect cabin class?<br/><i>economy / business / first</i>"]
    C --> A["🌐 Amadeus API Flight Search"]
    A --> R{"Results?"}
    
    R -->|"✅ Flights found"| P["Present options with pricing"]
    R -->|"❌ No results"| N["Offer: try different<br/>origin / date / cabin"]
    
    P --> U{"User action"}
    U -->|"Pick flight #2"| SEL["✈️ Flight selected<br/>Store raw_offer"]
    U -->|"First class flights"| C
    U -->|"Skip"| H["➡️ Proceed to Hotels"]
    
    SEL --> H
    
    style F fill:#16213e,color:#fff
    style A fill:#0f3460,color:#fff
    style SEL fill:#00b894,color:#fff
    style H fill:#6c63ff,color:#fff
```

**Flight Features:**
- **Auto round-trip:** If trip is multi-day, automatically assumes round-trip
- **Auto return date:** Departure date + trip duration = return date
- **Cabin class detection:** "First class flights" → re-routes to search, not treated as picking flight #1
- **Raw offer stored:** Full Amadeus offer saved for payment processing
- **Skip option:** User can skip flights entirely

---

## 📽️ Slide 11 — Hotel Selection

**Title:** Step 10 — Hotel Selection

**Visual:**

```mermaid
flowchart TB
    H["🏨 HOTEL_SELECTION Phase"]
    H --> HA["Hotel Agent runs<br/>with finalized stops + profile"]
    HA --> OP["🏨 Options presented<br/><i>3-5 hotels with details</i>"]
    
    OP --> U{"User picks"}
    
    U -->|"Hotel 2"| NUM["By number → select"]
    U -->|"The Marriott"| NAME["By name → fuzzy match"]
    U -->|"Looks good"| FIRST["Default → first hotel"]
    U -->|"Give me resorts"| CHANGE["🔄 Accommodation type change<br/>Re-run with new type"]
    
    NUM & NAME & FIRST & CHANGE --> BOOK["💳 BOOKING Phase"]
    
    subgraph HotelDetails["Each Hotel Shows"]
        D1["⭐ Rating & Reviews"]
        D2["🏷 Amenities (pool, wifi, spa...)"]
        D3["📍 Address & Maps Link"]
        D4["💡 Why Recommended"]
        D5["🏗 Accommodation Type"]
    end
    
    style H fill:#16213e,color:#fff
    style HA fill:#e94560,color:#fff
    style OP fill:#0f3460,color:#fff
    style CHANGE fill:#e94560,color:#fff
    style BOOK fill:#00b894,color:#fff
    style HotelDetails fill:#16213e,color:#fff
```

**Hotel Selection Process:**
- Runs **only after** itinerary stops are finalized (avoids wasted API calls)
- Hotel Agent searches the candidate pool matching the user's accommodation preferences
- Each hotel shows: name, rating, amenities, address, maps link, why-recommended
- User can pick by number, name, or accept default
- **Accommodation type change** re-runs hotel selection without restarting the flow

---

## 📽️ Slide 12 — Booking & Payment

**Title:** Step 11 — Final Booking & Payment

**Visual:**

```mermaid
flowchart TB
    BK["💳 BOOKING Phase"]
    BK --> SUM["📋 Trip Summary Presented"]
    
    SUM --> CHOICE{"User Chooses"}
    
    CHOICE -->|"1️⃣ Pay Now"| PAY["💳 Payment via Stripe"]
    CHOICE -->|"2️⃣ Do it Later"| LATER["⏸ Book through app"]
    
    PAY --> DONE["✅ COMPLETED Phase<br/><i>Terminal — no more changes</i>"]
    LATER --> DONE
    
    subgraph Summary["Trip Summary Content"]
        S1["✈️ Flight: EgyptAir MS123<br/>$450 USD"]
        S2["🏨 Hotel: Marriott Mena House<br/>$200/night × 5 = $1,000"]
        S3["💰 Total: $1,450 USD"]
        S4["🗓️ 5 days in Cairo"]
    end
    
    SUM --- Summary
    
    style BK fill:#16213e,color:#fff
    style SUM fill:#0f3460,color:#fff
    style PAY fill:#6c63ff,color:#fff
    style LATER fill:#0f3460,color:#fff
    style DONE fill:#00b894,color:#fff
    style Summary fill:#16213e,color:#fff
```

**Booking Data Sent to Flutter:**
```json
{
  "flight": { "airline": "EgyptAir", "flight_number": "MS123", "price": 450 },
  "hotel": { "name": "Marriott Mena House", "nightly_rate": 200, "total_cost": 1000 },
  "pricing": { "flight_cost": 450, "hotel_cost": 1000, "total_estimated": 1450 },
  "trip_summary": { "destination": "Cairo", "duration_days": 5 }
}
```

**🛑 Terminal Constraint:** One conversation = one trip. Once completed:
- Cannot start a new trip
- Cannot modify the existing itinerary
- Can only answer questions about the finalized trip

---

## 📽️ Slide 13 — Image Upload (Cross-Phase Feature)

**Title:** Bonus — Image-Powered Trip Planning

**Visual:**

```mermaid
flowchart LR
    U["👤 User uploads a photo"] --> V["📸 Gemini Vision<br/>Analyzes image"]
    V --> F["🔍 Extracted Features"]
    
    subgraph Features["Vision Features"]
        F1["🎯 Interests<br/><i>hiking, nature, beach</i>"]
        F2["🎨 Travel Style<br/><i>adventure, relaxation</i>"]
        F3["🏃 Pace<br/><i>moderate, packed</i>"]
        F4["💰 Budget Level<br/><i>budget, luxury</i>"]
    end
    
    F --> MERGE["🔄 Fuse with Profile<br/><i>multimodal_fusion.py</i>"]
    MERGE --> OUT["📋 Updated Trip Slots"]
    
    OUT --> PLAN["Orchestrator uses fused<br/>features for planning"]
    
    style U fill:#6c63ff,color:#fff
    style V fill:#e94560,color:#fff
    style F fill:#16213e,color:#fff
    style MERGE fill:#0f3460,color:#fff
    style OUT fill:#00b894,color:#fff
```

**Use Cases:**
- Upload a photo of a travel destination → AI detects interests
- Upload a food photo → AI detects cuisine preferences
- Can be done at **any phase** in the conversation
- Low-confidence images are gracefully ignored

---

## 📽️ Slide 14 — End-to-End Flow Summary

**Title:** Complete User Journey

**Visual:**

```mermaid
flowchart LR
    S1["💬 1. User Message<br/><i>Chat or Image</i>"] -->
    S2["🧠 2. Interpreter<br/><i>Intent + Slots</i>"] -->
    S3["📋 3. Slot Filling<br/><i>Data Collection</i>"] -->
    S4["🔍 4. Profile &<br/>Place Retrieval"] -->
    S5["🗺️ 5. AI Planning<br/><i>Itinerary Gen</i>"] -->
    S6["📐 6. Route Opt.<br/><i>OSRM</i>"] -->
    S7["✅ 7. Validation<br/><i>Quality Check</i>"]
    
    S7 --> S8["👤 8. Review &<br/>Modify"]
    
    S8 --> S9["✈️ 9. Flight<br/>Selection"]
    S8 --> S9
    
    S9 --> S10["🏨 10. Hotel<br/>Selection"]
    S10 --> S11["💳 11. Booking<br/>& Payment"]
    S11 --> S12["✅ 12. Completed<br/><i>Terminal</i>"]
    
    style S1 fill:#6c63ff,color:#fff
    style S2 fill:#e94560,color:#fff
    style S3 fill:#16213e,color:#fff
    style S4 fill:#0f3460,color:#fff
    style S5 fill:#e94560,color:#fff
    style S6 fill:#0f3460,color:#fff
    style S7 fill:#16213e,color:#fff
    style S8 fill:#6c63ff,color:#fff
    style S9 fill:#0f3460,color:#fff
    style S10 fill:#16213e,color:#fff
    style S11 fill:#e94560,color:#fff
    style S12 fill:#00b894,color:#fff
```

**Key Design Principles:**
1. ⚡ **Progressive Disclosure** — Never overwhelm the user; ask one question at a time
2. 🧠 **Single LLM Call** — One message interpreter replaces three separate calls
3. 🔄 **Edit Fallback Chain** — Surgical → Preference → Regeneration (optimal path first)
4. 🏨 **Late Hotel Selection** — Hotels chosen only after stops are finalized (avoids waste)
5. 🛑 **Terminal Phase** — One conversation produces exactly one trip
6. 📸 **Cross-Phase Vision** — Image analysis works at any stage

---

## 📋 How to Use These in Your Presentation

1. **Copy each slide section** into your preferred presentation tool
2. For Mermaid diagrams:
   - **Option A:** Visit [Mermaid Live Editor](https://mermaid.live/), paste the code, export as **PNG/SVG**
   - **Option B:** If your tool supports Mermaid (Notion, Obsidian, GitHub), paste the code directly
3. **Recommended export resolution:** 1920×1080 (16:9) for best quality in presentations
4. **Color palette reference:**
   - 🟣 Purple `#6c63ff` — User interactions
   - 🔴 Red `#e94560` — AI/LLM components
   - 🔵 Navy `#16213e` — Data/Storage layers
   - 🟢 Green `#00b894` — Success/Completion
   - 🌀 Dark blue `#0f3460` — Processing/API layers
