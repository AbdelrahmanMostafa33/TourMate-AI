# TourMate AI — Mobile App

> 📖 For the full project overview, architecture, API reference, and setup guides, see the **[main README](../README.md)**.

Cross-platform mobile application built with **Flutter** for the TourMate AI travel planning platform.

## Overview

The TourMate mobile app provides a complete travel planning experience:

- 💬 **AI-powered chat** — Real-time WebSocket chat with structured card UI for itineraries, hotel options, flight options, and bookings
- 🗓️ **Trip management** — Create, view, and manage trips throughout their lifecycle
- 📍 **Place discovery** — Browse and explore places (attractions, restaurants, hotels) with filters
- ✈️ **Flight booking** — Search and book flights via Amadeus (powered by Stripe)
- 🏨 **Hotel selection** — Browse and select hotel options during trip planning
- 💳 **Payments** — Stripe Payment Sheet integration for secure checkout
- ⭐ **Reviews** — Rate and review places you've visited
- 🔖 **Saved places** — Bookmark places for future trips
- 📸 **Image upload** — Upload travel photos for AI-powered preference analysis
- 🧑 **Profile** — Manage your travel persona and preferences

## Design System

The app uses a sophisticated design language built around:
- **Deep Royal Blue** `#1E3A8A` — authority, depth, premium feel
- **Midnight Navy** `#0F172A` — rich darkness, elegance
- **Sapphire Blue** `#2563EB` — refined accent, sparingly used

Inter font family with a clear typographic hierarchy.

## Quick Start

```bash
cd mobile

# Install dependencies
flutter pub get

# Generate code (freezed models, Retrofit clients)
dart run build_runner build --delete-conflicting-outputs

# Configure Firebase (place google-services.json in android/app/)
# Run the app
flutter run
```

## Project Structure

```
lib/
├── app/                        # App config, routing, theme
│   ├── app.dart               # MaterialApp with TourMate theme
│   ├── app_router.dart        # Named routes with fade transitions
│   └── app_theme.dart         # Complete design system (colors, typography, widgets)
├── core/                       # Shared infrastructure
│   ├── errors/                 # API result wrappers, error handling
│   ├── layout/                 # Main shell with bottom navigation
│   ├── network/                # Retrofit API client, Dio factory, DI
│   ├── theme/                  # Design tokens
│   ├── utils/                  # Image picker, country/city data
│   └── widgets/                # Reusable UI components
└── features/                   # Feature modules
    ├── auth/                   # Sign in/up, profile management
    ├── chat/                   # WebSocket chat with card rendering
    ├── trips/                  # Trip list, detail, create
    ├── explore/                # Place browsing with filters
    ├── places/                 # Place detail, reviews
    ├── saved/                  # Bookmarked places
    ├── flights/                # Flight search and booking
    ├── bookings/               # Booking management
    └── payments/               # Stripe Payment Sheet integration
```

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `flutter_bloc` | State management (Cubit pattern) |
| `freezed` | Immutable data classes with union types |
| `dio` + `retrofit` | Type-safe HTTP client |
| `get_it` | Dependency injection |
| `firebase_core` + `firebase_auth` | Firebase authentication |
| `web_socket_channel` | Real-time chat with structured protocol |
| `flutter_stripe` | Stripe Payment Sheet for secure payments |
| `flutter_map` | Map display for places |
| `image_picker` | Photo upload for AI analysis |
| `google_fonts` | Inter font family |
| `shimmer` | Premium loading animations |
| `flutter_markdown_plus` | Markdown rendering for chat messages |

## More Info

| Resource | Link |
|----------|------|
| 📖 **Main Project README** | [../README.md](../README.md) — architecture, features, API reference, tech stack |
| 🛠️ **Detailed Setup Guide** | [docs/SETUPS/MOBILE_SETUP.md](../docs/SETUPS/MOBILE_SETUP.md) — Flutter SDK, Android Studio, Firebase |
| ⚙️ **Backend Component** | [../backend/README.md](../backend/README.md) — FastAPI service overview |
