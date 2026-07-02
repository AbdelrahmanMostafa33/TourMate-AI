# Orchestrator Message Flow — plan_trip Request

> A Mermaid sequence diagram tracing a user's `plan_trip` message through the orchestrator, conversation state, pipeline agents, and external services.

```mermaid
---
title: plan_trip — Orchestrator Sequence Diagram
---
sequenceDiagram
    autonumber
    participant U as 👤 User
    participant O as 🧠 Orchestrator<br/>(_process_message)
    participant MI as 📨 Message Interpreter<br/>(interpret_message)
    participant CS as 💬 ConversationState<br/>(slots / phase / history)
    participant RM as 💾 Redis Memory
    participant IA as 🖼 Image Analyzer
    participant PL as 📋 Profile Loader
    participant PR as 🔍 Place Retriever
    participant CSco as 📊 Candidate Scorer
    plannerNote over O,CSco: LangGraph Pipeline (trip_graph.ainvoke)
    participant PA as 🤖 Planning Agent
    participant RO as 🗺 Route Optimizer
    participant IV as ✅ Itinerary Validator
    participant EX as 🌐 External (LLM / DB / OSRM)

    Note over U,EX: ─── PHASE 1: USER INPUT & INITIAL ROUTING ───

    U->>O: "Plan me a 2-day trip to Cairo"

    O->>RM: resume_or_create(user_id, session_id)
    RM-->>O: ConversationState (GREETING phase)

    O->>IA: analyze_travel_image(image_bytes) [if present]
    IA-->>O: VisionFeatures (optional)

    O->>MI: interpret_message(state, message)
    MI-->>O: RouterResult(action="plan_trip", extracted={...})

    O->>CS: slots.merge(extracted)
    O->>CS: add_user_message(message)

    alt Image with features
        O->>CS: fuse image interests into slots
    end

    Note over O,EX: ─── PHASE 2: SLOT FILLING CHECK ───

    O->>CS: slots.is_complete()
    CS-->>O: False (missing fields)

    O->>CS: transition_to(SLOT_FILLING)
    O-->>U: "What kind of trip? Where to, how many days...?"

    U->>O: "Cairo, 2 days, cultural trip"

    O->>MI: interpret_message(state, message)
    MI-->>O: RouterResult(action="plan_trip", extracted={city, duration, style})

    O->>CS: slots.merge(extracted)
    O->>CS: slots.is_complete()
    CS-->>O: True ✅

    Note over O,EX: ─── PHASE 3: PIPELINE KICKOFF ───

    O->>CS: transition_to(PLAN_GENERATION)
    O->>CS: plan_started_at = now()

    O->>O: _handle_plan_trip()

    alt Has complete slots
        O->>O: _build_profile_from_slots(slots, trip_id)
    else Has token
        O->>PL: load_trip_profile(trip_id, token)
        PL-->>O: TripProfile
    else No token
        O->>PL: load_mock_profile(trip_id)
        PL-->>O: TripProfile
    end

    alt Image features with confidence != low
        O->>O: fuse_image_with_profile(profile, image_features)
    end

    O->>O: Build initial TripState dict

    Note over O,EX: ─── PHASE 4: LANGGRAPH PIPELINE ───

    O->>PL: trip_graph.ainvoke(initial_state)

    rect rgb(240, 248, 255)
        Note over PL,IV: ── Node 1: Profile Loader ──
        PL->>PL: Load profile (from state or DB)
        PL-->>PR: state["profile"] set

        Note over PR,CSco: ── Node 2: Place Retriever ──
        PR->>EX: get_places_for_city("Cairo")
        EX-->>PR: List of all Cairo places

        PR->>EX: _compute_semantic_interest_subcats(interests, subcats)
        EX-->>PR: Set of matched subcategories
        PR->>PR: _apply_filters(all_places, preferences, interest_subcats)
        PR->>PR: _cap_candidates(filtered)
        PR-->>CSco: state["filtered_places"] set
        PR-->>CSco: state["matched_interest_subcats"] set

        Note over CSco,PA: ── Node 3: Candidate Scorer ──
        CSco->>EX: load_place_embeddings(place_ids)
        EX-->>CSco: Place vectors dict
        CSco->>EX: embed_query(preferences text)
        EX-->>CSco: Query vector
        CSco->>CSco: Score each place (popularity + embedding + proximity + rating)
        CSco->>CSco: _diversity_optimize(scored, interest_subcats)
        CSco-->>PA: state["candidate_places"] set (up to 30 attractions)

        Note over PA,RO: ── Node 4: Planning Agent ──
        PA->>PA: _trim_for_prompt(candidates)
        PA->>EX: invoke_with_fallback("planner", ..., structured_output=ItineraryPlan)
        EX-->>PA: Pydantic ItineraryPlan
        PA->>PA: Validate days count, hydrate stops
        PA-->>RO: state["draft_itinerary"] set
        PA-->>RO: state["planning_attempts"] += 1

        Note over RO,IV: ── Node 5: Route Optimizer ──
        RO->>EX: compute_day_matrix(stops)
        EX-->>RO: Travel time matrix (Mock OSRM)
        RO->>RO: Reorder stops, annotate travel times
        RO-->>IV: state["optimized_itinerary"] set

        Note over IV,O: ── Node 6: Itinerary Validator ──
        IV->>IV: run_programmatic_checks(optimized)
        IV->>EX: invoke_with_fallback("validator", ..., LLM prompt)
        EX-->>IV: Validation result {is_valid, score, issue, suggestion}
        IV->>IV: compute_all_metrics(optimized)
        IV-->>O: state["is_valid"] + state["validation"] set
    end

    alt Validation Failed & Retries Left
        Note over IV,PA: Edge: should_retry_or_end → "planner"
        PA->>PA: Read state["validation"].issue as retry feedback
        PA->>EX: invoke_with_fallback (retry with feedback)
        EX-->>PA: Improved ItineraryPlan
    end

    Note over O,EX: ─── PHASE 5: RESULT PROCESSING ───

    O->>O: Get optimized_itinerary, is_valid, validation from result_state

    alt is_valid and optimized
        O->>O: _format_itinerary(optimized) → success message
    else pipeline_error
        O->>O: "I ran into an issue... {pipeline_error}"
    else optimized only (validation failed, exhausted retries)
        O->>O: "The itinerary didn't pass quality checks..."
    else no itinerary
        O->>O: "I wasn't able to generate a complete itinerary..."
    end

    O->>CS: set_itinerary(optimized, candidate_places, filtered_places)
    O->>CS: add_assistant_message(message)

    O->>RM: save(state)
    O->>RM: extend_ttl(session_id)

    Note over O,EX: ─── PHASE 6: RESPONSE ───

    alt Chat (handle_chat)
        O-->>U: {response_type: "itinerary", message, itinerary, validation, explanation, agent_metrics}
    else Stream (handle_chat_stream)
        O-->>U: stream: session → progress events → phase → text chunks → result event → done
    end

    Note over U,EX: ─── PHASE 7: POST-APPROVAL (user says "approve") ───

    U->>O: "approve"

    O->>CS: transition_to(FLIGHT_SELECTION)
    O-->>U: "Would you like to book a flight? Where from?"

    U->>O: "From Dubai, on July 15"

    O->>O: search_flights_for_trip("Dubai", "Cairo", ...)
    O-->>U: Flight options presented

    U->>O: "Flight #2 looks good"

    O->>O: Store selected flight, process payment info
    O->>O: _run_hotel_selection_and_present()
    O->>A[Hotel Agent]: run_hotel_selection()
    A-->>O: Updated itinerary with hotel suggestions
    O->>CS: transition_to(HOTEL_SELECTION)
    O-->>U: Hotel options presented

    U->>O: "I'll take hotel #1"

    O->>CS: approve_itinerary()
    O->>CS: transition_to(COMPLETED)
    O-->>U: ✅ Trip approved! Full itinerary summary
```

## Flow Summary

| Phase | What Happens |
|---|---|
| **1. Input & Routing** | User message → Redis session load → message interpreter → action classification |
| **2. Slot Filling** | If missing required info → ask clarification → loop until complete |
| **3. Pipeline Kickoff** | Build profile from slots/DB → fuse image features → build TripState |
| **4. LangGraph Pipeline** | Profile → Retriever → Scorer → Planner → Optimizer → Validator (with optional retry) |
| **5. Result Processing** | Format message → save itinerary to state → save to Redis |
| **6. Response** | Return/stream response with itinerary, validation, metrics |
| **7. Post-Approval** | User approves → flight search → hotel selection → trip finalized |
