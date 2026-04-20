# TourMate AI — Data Layer Logic & Thinking

## The Core Idea in One Sentence

> **Collect all the place data ONCE from the internet, store it in your own database, and at runtime only query your own database — never the internet.**

---

## Why This Approach

Think of it like a restaurant:

```
BAD approach (what you had before):
  Customer orders food → Chef runs to the supermarket → 
  Buys ingredients → Comes back → Cooks → Serves
  
  Result: 45 minutes per order. Supermarket might be closed.

GOOD approach (what you need):
  Chef buys all ingredients every Monday morning →
  Stores them in the kitchen fridge →
  Customer orders → Chef grabs from fridge → Cooks → Serves
  
  Result: 10 minutes per order. Always available.
```

**The APIs (Overpass, Wikidata, Wikipedia) are your supermarket.
PostgreSQL is your fridge.
Gemini is your chef.**

---

## The Two Phases

### Phase A: Stocking the Fridge (Offline — runs once or periodically)

**When:** Before your demo. Then maybe weekly or monthly to keep data fresh.

**Who triggers it:** You (the admin), manually or on a schedule.

**What happens:**

```
Step 1 — COLLECT
    Go to Overpass API and ask:
    "Give me every museum, temple, monument, mosque, church,
     ruins, viewpoint, zoo, and attraction in these 15 Egyptian
     regions: Cairo, Luxor, Aswan, Alexandria, ..."
    
    You get back ~500-700 raw places with:
    - Name (Arabic + English)
    - GPS coordinates
    - Category (museum, ruins, etc.)
    - Sometimes a Wikidata ID
    - Sometimes opening hours
    
    This takes about 2-3 minutes total for all 15 regions.

Step 2 — ENRICH
    For each place that has a Wikidata ID:
        Ask Wikidata: "What is the English description of Q12193?"
        → "The Great Pyramid of Giza, oldest of the Seven Wonders"
    
    For each place:
        Ask Wikipedia: "Give me a 2-sentence summary of Karnak Temple"
        → "The Karnak Temple Complex comprises a vast mix of
           temples, pylons, and chapels. It is the largest
           religious building ever constructed."
    
    Also compute locally (no API needed):
        - Visit duration: based on category
          (museum = 90 min, viewpoint = 20 min, ruins = 75 min)
        - Significance score (1-5): places with Wikidata + Wikipedia
          get higher scores because they're more notable
    
    This takes about 3-5 minutes for all places.

Step 3 — STORE
    Put everything into your PostgreSQL database.
    If a place already exists (from a previous run), update it
    instead of creating a duplicate.
    
    This takes a few seconds.

TOTAL: ~5-8 minutes. Done. Your fridge is stocked.
```

**After this phase, your database contains something like:**

```
| Name                    | Region       | Category             | Duration | Significance | Description                          |
|-------------------------|--------------|----------------------|----------|-------------|--------------------------------------|
| Great Pyramid of Giza   | Cairo & Giza | archaeological_site  | 90 min   | 5           | The oldest of the Seven Wonders...   |
| Egyptian Museum          | Cairo & Giza | museum               | 120 min  | 5           | Houses the world's largest...        |
| Karnak Temple            | Luxor        | archaeological_site  | 90 min   | 5           | The largest religious building...    |
| Khan el-Khalili          | Cairo & Giza | attraction           | 60 min   | 4           | Famous bazaar in Islamic Cairo...    |
| Temple of Philae         | Aswan        | archaeological_site  | 75 min   | 5           | Island temple dedicated to Isis...   |
| Blue Hole                | Dahab        | attraction           | 45 min   | 4           | World-famous diving site...          |
| ... 594 more rows ...    |              |                      |          |             |                                      |
```

---

### Phase B: Cooking the Meal (Runtime — every user request)

**When:** Every time a user asks for a trip.

**What happens:**

```
User says: "I want to explore ancient temples near Luxor for 2 days"

Step 1 — UNDERSTAND WHAT THEY WANT
    Parse their message to extract:
    - Region: Luxor
    - Interests: ancient, temples
    - Duration: 2 days
    
    Map "ancient" and "temples" to database categories:
    → archaeological_site, ruins, place_of_worship

Step 2 — QUERY YOUR OWN DATABASE (not the internet!)
    Ask PostgreSQL:
    "Give me all places in Luxor where category is
     archaeological_site, ruins, or place_of_worship,
     ordered by significance score, limit 25"
    
    PostgreSQL returns 18 matching places in under 5 milliseconds.
    
    These 18 places include Karnak, Luxor Temple, Valley of the Kings,
    Hatshepsut Temple, Medinet Habu, etc.

Step 3 — FORMAT FOR THE LLM
    Turn those 18 places into a compact text block:
    "1. Karnak Temple - archaeological_site - 90 min - 
        The largest religious building ever constructed..."
    "2. Valley of the Kings - archaeological_site - 120 min -
        Royal burial ground for pharaohs..."
    ...
    
    This text is roughly 1,500 tokens.
    (Compared to 50,000+ if you tried to send ALL of Egypt)

Step 4 — SEND TO GEMINI
    Give Gemini:
    - The 18 filtered places (from your DB)
    - The user's request
    - The user's behavioral profile
    - Instructions to rank, schedule, and narrate
    
    Gemini returns a structured 2-day itinerary.

Step 5 — ROUTING (OSRM)
    For the places Gemini selected, ask OSRM:
    "How long does it take to drive from Karnak to Luxor Temple?"
    → 8 minutes
    
    This validates that the itinerary is physically feasible.

TOTAL RUNTIME: 5-13 seconds. Acceptable.
```

---

## What the LLM Sees vs What Exists

This is the key insight:

```
Your database has:          600 places across all of Egypt
PostgreSQL filters to:       18 places relevant to this specific query
Gemini receives:             18 places (compact text, ~1,500 tokens)
Gemini selects and ranks:    8-10 places for the final itinerary

The LLM never sees all 600. It only sees the 18 that survived filtering.
The database does the heavy lifting. The LLM does the creative work.
```

---

## Why Not Just Use APIs at Runtime

```
Problem 1: SPEED
  APIs at runtime     = 35-73 seconds per request
  Local DB at runtime = 5-13 seconds per request

Problem 2: RELIABILITY
  You already got 504 Gateway Timeout errors twice.
  If that happens during your graduation demo, it's a disaster.
  Your own database never times out.

Problem 3: RATE LIMITS
  Overpass will throttle you if 5 users hit it at the same time.
  Your database handles 1000 concurrent queries without blinking.

Problem 4: CUSTOM DATA
  APIs give you raw geographic data.
  Your database can have YOUR data:
  - Curated descriptions
  - Accurate visit durations
  - Significance scores for prioritization
  - Local tips you write manually
  - Categories matched to YOUR profiling system
  
  None of this exists in Overpass or Wikidata.

Problem 5: TOKEN LIMITS
  If you query Overpass live and get 600 places, you can't send
  all 600 to Gemini. It's too many tokens. You'd have to filter
  anyway. So why not filter BEFORE the API call — from a DB?
```

---

## What Data You're Actually Storing

For each place, you store:

```
IDENTITY
  - Name (Arabic)
  - Name (English)
  - Region (Cairo & Giza, Luxor, Aswan, etc.)
  - Category (museum, archaeological_site, ruins, monument, 
              place_of_worship, viewpoint, attraction, etc.)

LOCATION
  - Latitude
  - Longitude

CONTENT (this is what makes your DB valuable)
  - Description (from Wikipedia/Wikidata, 2-3 sentences)
  - Visit duration in minutes (computed from category)
  - Significance score 1-5 (computed from data completeness)
  - Opening hours (from OpenStreetMap, often incomplete)
  - Website (if available)

SOURCE TRACKING
  - OSM ID (to avoid duplicates)
  - Wikidata ID (to link back to source)
  - When the record was created
  - When it was last updated
```

---

## How the Significance Score Works

This is important for your itinerary prioritization (requirement #11):

```
Score 5: Must-see landmark
  - Has Wikidata ID ✓
  - Has Wikipedia summary ✓  
  - Has description ✓
  - Examples: Pyramids, Karnak, Egyptian Museum, Abu Simbel

Score 4: Major attraction
  - Has Wikidata ID ✓
  - Has some description ✓
  - Missing one data source
  - Examples: Khan el-Khalili, Philae Temple, Blue Hole

Score 3: Notable place
  - Has basic info
  - Missing enrichment data
  - Examples: Smaller mosques, local museums

Score 2: Minor place
  - Name and location only
  - No description available
  - Examples: Small viewpoints, unmarked historical sites
```

When the LangGraph agent builds an itinerary, it can say:
"For a 2-day trip, prioritize significance 5 places first,
then fill remaining time with significance 4 places."

---

## How Filtering Works at Runtime

The database lets you answer any user query instantly:

```
"Temples in Luxor"
  → Filter: region = Luxor, category IN (archaeological_site, ruins)
  → Returns: ~12 places

"Museums in Cairo for kids"
  → Filter: region = Cairo & Giza, category IN (museum, zoo, theme_park)
  → Returns: ~15 places

"Best diving spots"
  → Filter: region IN (Dahab, Sharm el-Sheikh, Hurghada, Marsa Alam),
            category = attraction
  → Returns: ~20 places

"Plan a week-long tour of all Egypt"
  → Filter: significance >= 4 (only top places)
  → Returns: ~40 places across all regions

"What's near me?" (user shares GPS)
  → Filter: within 15km of user's coordinates
  → Returns: whatever is nearby, sorted by distance
```

Each of these queries takes under 5 milliseconds.

---

## How the Interest-to-Category Mapping Works

Users don't say "archaeological_site." They say "temples" or "history."
You need a mapping layer:

```
User says "history"    → DB categories: archaeological_site, ruins, 
                                         monument, memorial, museum

User says "temples"    → DB categories: archaeological_site, ruins,
                                         place_of_worship

User says "museums"    → DB categories: museum, gallery

User says "religious"  → DB categories: place_of_worship

User says "nature"     → DB categories: viewpoint, attraction

User says "family"     → DB categories: zoo, theme_park, museum,
                                         attraction

User says "adventure"  → DB categories: attraction, viewpoint, 
                                         theme_park
```

---

## How the Region Keyword Matching Works

Users don't say "Cairo & Giza." They say "Cairo" or "pyramids."
You need another mapping:

```
User says "cairo"      → Region: Cairo & Giza
User says "pyramids"   → Region: Cairo & Giza
User says "sphinx"     → Region: Cairo & Giza
User says "luxor"      → Region: Luxor
User says "karnak"     → Region: Luxor
User says "aswan"      → Region: Aswan
User says "sharm"      → Region: Sharm el-Sheikh
User says "dahab"      → Region: Dahab
```

---

## When to Re-Run the Pipeline

```
MUST run:
  - Before your first demo
  - After adding new regions

SHOULD run:
  - Weekly or monthly to catch new places added to OpenStreetMap
  - After you manually curate/edit descriptions

WHAT HAPPENS when you re-run:
  - New places get added
  - Existing places get updated (if better description found)
  - No duplicates created (because of the unique OSM ID constraint)
  - The run is logged (when it ran, how many places, success/failure)
```

---

## What OSRM Does (Separate from the Database)

OSRM is the one API you DO call at runtime, and that's fine because:

```
Purpose: Calculate driving/walking time between two GPS points
Example: "How long from Karnak Temple to Valley of the Kings?"
         → 25 minutes by car

Why it's OK at runtime:
  - It's extremely fast (< 200ms per route)
  - It's self-hostable (you can run it locally)
  - Each query is tiny (just two coordinates)
  - You only call it for the 8-10 stops in the final itinerary,
    not for 600 places

Why you can't pre-compute it:
  - 600 places × 600 places = 360,000 possible routes
  - That's too many to store
  - You only need routes between places in the SAME itinerary
```

---

## Summary: The Data Flow Mental Model

```
ONCE (offline):
  Internet APIs → Pipeline → PostgreSQL (your fridge)

EVERY REQUEST (runtime):
  User question
      ↓
  Parse intent (region + interests + duration)
      ↓
  Query YOUR database (5ms, always works)
      ↓
  Get 20-40 relevant places
      ↓
  Format as compact text (~1,500 tokens)
      ↓
  Send to Gemini with user profile
      ↓
  Gemini builds the itinerary
      ↓
  OSRM validates travel times
      ↓
  Show to user (total: 5-13 seconds)
```

**Save this. Come back to it when you're ready to implement.**s