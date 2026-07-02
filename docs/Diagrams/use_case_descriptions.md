# TourMate AI — Use Case Descriptions

> High-level descriptions derived from the system's use case diagram, architecture, and sequence diagrams.

---

## UC#1 — Authenticate & Manage Account

**Actors:** Traveler

**Pre-Condition:** The traveler has not yet signed up or logged in.

**Post-Condition:** The traveler is authenticated and can access all protected features of the platform.

**Main Flow (Sign Up)**
1. The traveler creates an account by providing their email address and a password.
2. The system verifies their identity and creates a secure account.
3. The traveler is logged in and can start using the platform.

**Alternative Flow A (Login)**
1. A returning traveler logs in using their email and password.
2. The system verifies the credentials and grants access.
3. The traveler's session is maintained so they don't need to log in repeatedly.

**Alternative Flow B (Session Continuation)**
1. If the traveler's session expires, the system automatically refreshes it without requiring re-login.
2. The traveler continues using the platform seamlessly.

**Alternative Flow C (Login Failure)**
1. If the traveler enters incorrect credentials or a network issue occurs, the system notifies them and allows them to retry.

**Exceptions**
- Network issues prevent authentication — the traveler is asked to try again later.
- The traveler tries to sign up with an email that is already registered — the system prompts them to log in instead.

**Notes**
- Protected features (trip planning, bookings, reviews, saved places) require authentication.
- Browsing and discovering places is publicly accessible without an account.

---

## UC#2 — Manage Trips & Itineraries

**Actors:** Traveler

**Pre-Condition:** The traveler is logged in.

**Post-Condition:** A trip is created and moves through its natural lifecycle (planning, itinerary ready, booking, in progress, completed, or cancelled).

**Main Flow (Create & View Trip)**
1. The traveler starts a conversation with the AI and describes the trip they want — for example, "Plan me a weekend trip to Cairo."
2. The AI creates a new trip with the chosen destination and dates, and the trip begins in the planning phase.
3. The traveler can view their active trips at any time through the trips list, with full details about each trip's itinerary, bookings, and status.

**Alternative Flow A (Approve Itinerary)**
1. The AI generates a day-by-day itinerary and presents it directly in the chat conversation.
2. The traveler reviews the itinerary in the chat and gives approval by typing their confirmation.
3. The itinerary is marked as approved and the trip moves toward the booking phase, where flight and hotel selection becomes available through the chat.

**Alternative Flow B (Cancel Trip)**
1. The traveler decides to cancel a trip at any stage by requesting it through the chat.
2. The system marks the trip as cancelled and releases any associated bookings.
3. The trip is removed from the active trips list.

**Alternative Flow C (View Trip Details)**
1. The traveler selects a specific trip from their trips list to see its full details.
2. The system shows the complete itinerary, booked flights, accommodation, and payment status.

**Notes**
- Trips are created through the chat conversation when the traveler first describes their trip to the AI.
- Itinerary approval happens within the chat — the traveler simply confirms their approval in conversation.
- A trip progresses through stages: planning → itinerary ready → booking pending → confirmed → in progress → completed or cancelled.
- If a payment fails, the trip enters a recoverable state so the traveler can retry without losing progress.
- Each trip contains one itinerary with multiple days and stops.

---

## UC#3 — Chat with AI & Plan Trip

**Actors:** Traveler

**Pre-Condition:** The traveler is logged in and connected to the chat session.

**Post-Condition:** The AI generates a personalized day-by-day itinerary based on the traveler's preferences.

**Main Flow (Plan a New Trip)**
1. The traveler opens the chat and describes their trip in natural language — for example, "Plan me a 2-day trip to Cairo."
2. The AI interprets the request and checks if all key details are covered (destination, duration, travel style, budget).
3. If information is missing, the AI asks clarifying questions until everything is clear.
4. Once all details are collected, the AI engine works through several steps:
   - Loads the trip's preferences and profile
   - Searches for relevant places (attractions, restaurants, hotels) matching the traveler's interests
   - Scores and ranks these places by popularity, relevance, proximity, and diversity
   - Generates a logically sequenced day-by-day itinerary
   - Optimizes the route for minimal travel time between stops
   - Validates the itinerary for quality and completeness
5. The itinerary is streamed back to the traveler in real time.
6. If the itinerary doesn't meet quality standards, the AI automatically retries and improves it.

**Alternative Flow A (Refine Preferences)**
1. The traveler says, "Make this trip more cultural" or similar preference adjustments.
2. The AI reranks the places to better match the updated preferences and presents a revised itinerary.

**Alternative Flow B (Edit a Specific Activity)**
1. The traveler requests a specific change — for example, "Add a museum to day 1" or "Remove the Eiffel Tower."
2. The AI surgically modifies the itinerary by adding, removing, or swapping the requested activity.
3. The updated itinerary is presented to the traveler.

**Alternative Flow C (Regenerate the Entire Plan)**
1. The traveler decides they want a completely different plan — for example, "Actually, I hate museums. Regenerate the trip without them."
2. The AI re-runs the full planning pipeline with the new preferences and generates an entirely new itinerary.

**Alternative Flow D (General Conversation)**
1. The traveler asks a general question, such as "What's the weather like in Paris?"
2. The AI responds conversationally without triggering the trip planning pipeline.

**Alternative Flow E (Use a Photo for Inspiration)**
1. The traveler uploads a travel photo to express their style preferences.
2. The AI analyzes the image to understand the traveler's aesthetic tastes and interests.
3. These visual preferences are incorporated into the trip planning process.

**Exceptions**
- If the AI service is temporarily unavailable, the system falls back to an alternative provider.
- If the chat session is interrupted, the conversation state is preserved so the traveler can resume where they left off.

**Notes**
- The AI supports three editing modes: preference refinement (fast), specific activity edits, and full regeneration (most expensive).
- All AI actions are tracked for quality assurance and cost monitoring.
- The itinerary is validated both programmatically and by AI before being presented.

---

## UC#4 — Explore & Discover Places

**Actors:** Traveler

**Pre-Condition:** The places database contains attractions, restaurants, and hotels. The traveler may or may not be logged in.

**Post-Condition:** The traveler finds places of interest and can view their full details.

**Main Flow (Browse Explore)**
1. The traveler opens the Explore tab and sees suggested locations with category tabs (attractions, restaurants, hotels).
2. The system displays a paginated list of places with photos, ratings, and basic information.
3. The traveler scrolls through results and browses at their own pace.

**Alternative Flow A (Filter by Category)**
1. The traveler selects a category tab — for example, "Restaurants."
2. The system shows only places belonging to that category.
3. For hotels, the traveler can further filter by type (hotel, hostel, resort).

**Alternative Flow B (Search by City)**
1. The traveler types a city name — for example, "Cairo."
2. The system suggests matching locations, and the traveler selects one.
3. The system displays places in that city.

**Alternative Flow C (View Place Details)**
1. The traveler taps on a place card to learn more.
2. The system shows full details: description, photos, address, location on map, pricing, and ratings.

**Alternative Flow D (Search in Natural Language)**
1. The traveler searches using descriptive text — for example, "romantic dinner with sea view."
2. The system finds places that best match the description and ranks them by relevance.

**Notes**
- Browsing places is publicly available without needing an account.
- Categories available: attractions, restaurants, and hotels.
- The AI engine uses place search internally when building itineraries.

---

## UC#5 — Book Flights

**Actors:** Traveler

**Pre-Condition:** The traveler is logged in, has a trip planned, and the itinerary is approved.

**Post-Condition:** A flight booking is created via Amadeus and awaits payment confirmation.

**Main Flow (Search, Select, Book, Pay)**
1. After the itinerary is approved, the AI presents available flight options within the chat conversation, with the destination and dates already pre-filled from the trip.
2. The traveler tells the AI their departure city.
3. The system searches for real-time flight availability and pricing through the Amadeus service.
4. Available flight options are presented in the chat with prices, times, and airlines.
5. The traveler selects a flight by chatting their choice.
6. The system prepares a payment through the secure checkout presented within the conversation.
7. The traveler completes payment through their preferred method.
8. The system verifies the payment and books the flight through Amadeus, then shows the traveler a confirmation in the chat.

**Alternative Flow A (City Autocomplete)**
1. The traveler starts typing a city name in the chat.
2. The system suggests matching airports and cities to help them choose the right one.

**Alternative Flow B (Cancel a Booking)**
1. The traveler requests to cancel a booked flight through the chat.
2. The system cancels the reservation.

**Alternative Flow C (Round-Trip by Default)**
1. If the traveler doesn't specify a return date, the system automatically uses the trip's end date.
2. Round-trip flights are searched by default, saving the traveler an extra step.

**Exceptions**
- If no flights are available for the chosen route, the system informs the traveler in the chat and suggests alternatives.
- If payment succeeds but the Amadeus booking fails, the traveler is guided through the refund process within the conversation.

**Notes**
- Flight booking is handled entirely within the chat conversation — no separate booking page.
- City names are resolved to airport codes automatically behind the scenes for a smooth experience.
- Flight search and booking use the Amadeus test environment with real airline data.
- Payment is processed through a secure checkout in test mode — no real financial transactions take place.
- The booking flow uses a two-step process (initiate payment → confirm) to handle mobile payments reliably.

---

## UC#6 — Book Hotels

**Actors:** Traveler

**Pre-Condition:** The traveler is logged in, the itinerary is approved, and accommodation options have been suggested by the AI.

**Post-Condition:** A simulated hotel booking is created and ready for payment confirmation.

**Main Flow (Select Hotel & Book)**
1. After the itinerary is approved, the AI presents recommended hotel and accommodation options directly in the chat conversation.
2. The traveler selects a hotel by chatting their choice, along with preferred check-in and check-out dates.
3. The system creates a simulated booking with a confirmation number and provider details, then records it under the trip.
4. The booking is now ready for the traveler to proceed with payment.

**Alternative Flow A (Book All Accommodations at Once)**
1. The traveler requests to book accommodation for every stop in their itinerary in one go through the chat.
2. The system creates simulated bookings for all stops and transitions the trip to booking pending.

**Alternative Flow B (Cancel a Booking)**
1. The traveler cancels a hotel booking by requesting it in the chat.
2. The system cancels the reservation without proceeding to payment.

**Alternative Flow C (Mark Booking as Completed)**
1. After the trip visit, the traveler (or the system) marks confirmed bookings as completed.

**Exceptions**
- If the hotel provider is unreachable, the system falls back to locally matched accommodation suggestions without creating a real booking.

**Notes**
- Hotel booking is handled entirely within the chat conversation — no separate booking page.
- The booking must be paid before it is confirmed; payment is a separate step managed after booking.
- Hotel bookings are simulated — the system generates realistic confirmation numbers and provider details without connecting to a live hotel booking API.
- The system supports booking accommodation for multiple stops at once to save the traveler time.

---

## UC#7 — Manage Payments

**Actors:** Traveler

**Pre-Condition:** The traveler is logged in and has at least one unpaid booking (flight or hotel) associated with their trip.

**Post-Condition:** The payment is processed and the booking is confirmed (flight via Amadeus, hotel via simulated confirmation), or the payment fails and the traveler can retry.

**Main Flow (Pay for a Single Booking)**
1. After a booking is created, the system presents a secure checkout option within the chat conversation.
2. The traveler chooses their payment method and completes the transaction.
3. The system processes the payment through a secure test environment and verifies it.
4. The booking is marked as confirmed, and the trip status is updated.

**Alternative Flow A (Pay All Pending Bookings at Once)**
1. The traveler requests to pay for all their pending bookings together through the chat.
2. The system processes payments for everything in a single flow.
3. When all payments succeed, the trip is confirmed.

**Alternative Flow B (Pay for Flights and Hotels in One Go)**
1. The traveler has both flight and hotel bookings pending and chooses to settle everything together.
2. The system presents a combined checkout covering all bookings under the trip.
3. After payment, each booking is confirmed individually — the flight through Amadeus and the hotel through simulated confirmation — and the trip status is updated once all are paid.

**Alternative Flow C (Payment Failure Recovery)**
1. The traveler's payment attempt fails.
2. The trip enters a recoverable state — no progress is lost.
3. The traveler can retry the payment through the chat when ready.

**Exceptions**
- If the payment service is unavailable, the system falls back to a fully simulated payment — no secure connection needed.
- If a payment succeeds but the booking confirmation fails (e.g., Amadeus error), the traveler is guided through the refund process.

**Notes**
- Payment is managed as a separate step after booking — the traveler books first, then pays.
- All payments run in Stripe sandbox (test mode) — no real financial transactions take place.
- If Stripe is not configured, the system falls back to a fully simulated payment with no external calls.
- Payments can be handled individually per booking or batched together for convenience.
- The system processes payments both synchronously (client confirms after payment sheet) and asynchronously (via webhook).
- Hotel bookings are simulated; flight bookings are real through the Amadeus test environment.

---

## UC#8 — Review Places & Give Feedback

**Actors:** Traveler

**Pre-Condition:** The traveler is logged in and has visited a place they want to review.

**Post-Condition:** A review with a rating and comment is published for other travelers to see.

**Main Flow (Write a Review)**
1. The traveler navigates to a place's detail page and views existing reviews.
2. The traveler taps "Write a Review" and submits a rating along with a comment.
3. The system publishes the review, making it visible to other users.

**Alternative Flow A (Update a Review)**
1. The traveler returns to their existing review and updates the rating or comment.
2. The system saves the changes.

**Alternative Flow B (Delete a Review)**
1. The traveler removes their review entirely.
2. The system deletes the review and its associated likes.

**Alternative Flow C (View My Reviews)**
1. The traveler opens their personal review history.
2. The system shows all reviews they have written across different places.

**Alternative Flow D (Like a Review)**
1. The traveler finds a review helpful and taps the like button.
2. The system records the like. Tapping again removes it (toggle).

**Exceptions**
- If the traveler tries to review the same place twice, the system notifies them that they already have a review.
- Travelers can only edit or delete their own reviews.

**Notes**
- Only one review per user per place is allowed.
- Reviews are shown with the most recent first.
- Average ratings are calculated dynamically based on all reviews.

---

## UC#9 — Save & Manage Places

**Actors:** Traveler

**Pre-Condition:** The traveler is logged in and has found a place they are interested in.

**Post-Condition:** The place is saved to the traveler's personal list for future reference.

**Main Flow (Save a Place)**
1. The traveler is viewing a place — from search results, an itinerary, or the explore page.
2. The traveler taps the bookmark or save button.
3. The system adds the place to the traveler's saved list.

**Alternative Flow A (View Saved Places)**
1. The traveler opens their saved places list.
2. The system shows all bookmarked places with their full details, sorted by most recently saved.

**Alternative Flow B (Unsave a Place)**
1. The traveler taps the unsave button on a previously saved place.
2. The system removes it from their saved list.

**Alternative Flow C (Save with a Note)**
1. When saving a place, the traveler adds a personal note — for example, "Must visit this!"
2. The note is stored alongside the saved place for the traveler's reference.

**Notes**
- Saved places are personal bookmarks, separate from the itinerary.
- Duplicate saves are prevented — a place can only be saved once.
- Places are shown most recently saved first.

---

## UC#10 — Upload & Analyze Images

**Actors:** Traveler

**Pre-Condition:** The traveler is logged in and has a trip to associate images with.

**Post-Condition:** Travel photos are uploaded, their content is analyzed, and extracted preferences are used to enhance trip recommendations.

**Main Flow (Upload Photo for Travel Inspiration)**
1. The traveler uploads a travel-related photo, either during the chat or from their gallery.
2. The system saves the image and runs AI analysis to understand what the photo reveals about the traveler's interests and style.
3. If the confidence is high enough, the extracted preferences are incorporated into the trip planning process.
4. When the itinerary is generated, it reflects visual cues from the uploaded photos.

**Alternative Flow A (View Trip Gallery)**
1. The traveler opens the media gallery for a specific trip.
2. The system shows all uploaded images with their details.

**Alternative Flow B (Delete an Image)**
1. The traveler removes an image from the gallery.
2. The system deletes the image and its extracted data.

**Exceptions**
- If image analysis fails (corrupt file or service issue), the system logs the error and continues without extracting preferences.
- Unsupported image formats are rejected with a clear message.

**Notes**
- AI vision analysis extracts travel style cues, interests, and location hints from photos.
- Only high-confidence preferences are applied to trip planning; low-confidence insights are stored but not used.
- Image analysis runs in the background so it doesn't slow down the chat experience.

---

## UC#11 — Monitor System Health

**Actors:** System Administrator

**Pre-Condition:** The system is running and connected to monitoring tools.

**Post-Condition:** The administrator has visibility into system health, AI performance, and operational metrics. No system state is changed.

**Main Flow (Health Check)**
1. The administrator or an automated monitoring service checks whether the system is alive and responding.
2. The system confirms it is healthy and operational.

**Alternative Flow A (Review AI Performance Traces)**
1. The administrator inspects detailed traces of AI pipeline runs.
2. Each step of the AI engine (profile loading, place retrieval, planning, validation) is visible with timing, inputs, and outputs.
3. This helps debug issues and understand how the AI reached its decisions.

**Alternative Flow B (Monitor Token Usage & Costs)**
1. The administrator views token consumption reports.
2. Per-trip and per-agent token usage is available to track costs and detect unusual spikes.

**Alternative Flow C (View Performance Metrics)**
1. The administrator checks latency, error rates, and usage trends for each AI agent.
2. Historical data helps with capacity planning and identifying slow or failing components.

**Alternative Flow D (Review System Logs)**
1. The administrator queries system logs to investigate errors, warnings, and key events.
2. Logs help diagnose production issues and track system behavior.

**Notes**
- The health check is a lightweight status indicator and does not verify every external dependency.
- AI actions are fully traceable for debugging and auditing purposes.
- Token usage is tracked per trip to identify which parts of the AI pipeline are most expensive.
- All monitoring infrastructure is internal; there is no public admin dashboard.
