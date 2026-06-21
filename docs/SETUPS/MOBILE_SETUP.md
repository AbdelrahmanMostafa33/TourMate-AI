# TourMate AI — Mobile Setup Guide (Flutter + Android Studio)

> Complete guide for setting up the Flutter mobile app from scratch after cloning the repo for the first time.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install Flutter SDK](#2-install-flutter-sdk)
3. [Install Android Studio](#3-install-android-studio)
4. [Configure Android Studio for Flutter](#4-configure-android-studio-for-flutter)
5. [Set Up an Android Emulator](#5-set-up-an-android-emulator)
6. [Clone the Repository](#6-clone-the-repository)
7. [Open the Project in Android Studio](#7-open-the-project-in-android-studio)
8. [Install Flutter Dependencies](#8-install-flutter-dependencies)
9. [Firebase Setup (google-services.json)](#9-firebase-setup-google-servicesjson)
10. [Configure the Backend URL](#10-configure-the-backend-url)
11. [Run the App](#11-run-the-app)
12. [Run on a Physical Android Device](#12-run-on-a-physical-android-device)
13. [Project Structure Overview](#13-project-structure-overview)
14. [Key Dependencies](#14-key-dependencies)
15. [Common Errors & Fixes](#15-common-errors--fixes)
16. [Quick-Start Checklist](#16-quick-start-checklist)

---

## 1. Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Android Studio | Hedgehog (2023.1.1) or newer | https://developer.android.com/studio |
| Flutter SDK | 3.19.x or newer | https://docs.flutter.dev/get-started/install |
| Dart SDK | ^3.9.2 (bundled with Flutter) | included with Flutter |
| Java (JDK) | 17 (bundled with Android Studio) | bundled — no separate install needed |
| Git | Latest | https://git-scm.com/downloads |

> ⚠️ **Do NOT install Flutter from the Microsoft Store** — it causes PATH issues on Windows. Always use the official zip from flutter.dev.

---

## 2. Install Flutter SDK

### Windows

1. Go to https://docs.flutter.dev/get-started/install/windows
2. Download the latest **stable** Flutter SDK `.zip`
3. Extract it to a folder **without spaces or special characters** in the path:
   ```
   ✅  C:\dev\flutter
   ❌  C:\Program Files\flutter        (has spaces)
   ❌  C:\Users\My Name\flutter        (has spaces)
   ```
4. Add Flutter to your PATH:
   - Search **"Environment Variables"** in the Start menu
   - Under **User variables**, find `Path` → click **Edit**
   - Click **New** → paste `C:\dev\flutter\bin`
   - Click OK on all dialogs

5. Open a **new** PowerShell window and verify:
   ```powershell
   flutter --version
   # Should print: Flutter 3.x.x • channel stable
   ```

### Linux

```bash
sudo snap install flutter --classic
flutter --version
```

### macOS

```bash
brew install --cask flutter
flutter --version
```

---

## 3. Install Android Studio

1. Download from https://developer.android.com/studio
2. Run the installer — keep all default options
3. On first launch, go through the **Setup Wizard**:
   - Choose **Standard** installation
   - Accept all license agreements
   - Let it download the Android SDK (this takes a few minutes)

---

## 4. Configure Android Studio for Flutter

### Install the Flutter and Dart plugins

1. Open Android Studio
2. Go to **File → Settings** (Windows/Linux) or **Android Studio → Preferences** (macOS)
3. Navigate to **Plugins**
4. Search for **Flutter** → click **Install**
   - This automatically installs the **Dart** plugin too
5. Click **Restart IDE** when prompted

### Tell Flutter where Android Studio lives

Back in PowerShell/Terminal:

```bash
flutter config --android-studio-dir "C:\Program Files\Android\Android Studio"
```

> Adjust the path if you installed Android Studio somewhere else.

### Accept Android licenses

```bash
flutter doctor --android-licenses
# Press 'y' and Enter for each license prompt
```

### Run the full doctor check

```bash
flutter doctor
```

All checkmarks should be green. The expected output:

```
[✓] Flutter (Channel stable, 3.x.x)
[✓] Android toolchain - develop for Android devices
[✓] Android Studio (version 2023.x)
[✓] VS Code (optional)
[✓] Connected device
[!] Network resources (optional — skip if offline)
```

> If you see `[!]` next to anything, read the message — `flutter doctor` tells you exactly what command to run to fix it.

---

## 5. Set Up an Android Emulator

You need a virtual device to test the app without a physical phone.

1. In Android Studio, go to **Tools → Device Manager**
2. Click **Create Device**
3. Choose a device definition — recommended: **Pixel 7** → Next
4. Choose a system image — recommended: **API 34 (Android 14)** → download if needed → Next
5. Leave all defaults → **Finish**
6. Click the ▶️ button next to the device to start it

> The emulator takes ~1 minute to boot the first time. Leave it running while you work.

---

## 6. Clone the Repository

```bash
git clone https://github.com/AbdooMatrix/TourMate-AI.git
cd TourMate-AI/mobile
```

---

## 7. Open the Project in Android Studio

1. Open Android Studio
2. Click **Open** (not "New Project")
3. Navigate to the `mobile/` folder inside the cloned repo
4. Select the folder and click **OK**

> **Important:** Open the `mobile/` folder — not the repo root and not the `android/` subfolder inside it.

Android Studio will detect it as a Flutter project and show the Flutter toolbar at the top.

---

## 8. Install Flutter Dependencies

All Flutter packages are listed in `pubspec.yaml`. Install them with:

```bash
# Make sure you're inside the mobile/ folder
flutter pub get
```

You should see output ending with:

```
Got dependencies!
```

> If you see `pubspec.yaml not found`, you're in the wrong directory.

### Generate code (freezed models, Retrofit clients)

The project uses code generation for immutable models and API clients. After installing dependencies, run:

```bash
dart run build_runner build --delete-conflicting-outputs
```

> Re-run this command whenever you modify a freezed model or Retrofit interface.

---

## 9. Firebase Setup (google-services.json)

The app uses Firebase for authentication. You need to add a config file that is **not stored in Git**.

### Get the file

1. Go to https://console.firebase.google.com
2. Open the **TourMate** project (ask the team for access)
3. Click the ⚙️ gear icon → **Project Settings**
4. Scroll to **Your apps** → select the Android app
5. Click **Download google-services.json**

### Place the file

Put it here — **exactly** this location:

```
mobile/
└── android/
    └── app/
        └── google-services.json   ← HERE
```

> ⚠️ **Never commit this file to Git.** It is already in `.gitignore`.

### Verify the package name matches

Open `google-services.json` and check the `package_name` field:

```json
"package_name": "com.example.tourmate"
```

Open `mobile/android/app/build.gradle.kts` and confirm `applicationId` matches:

```kotlin
applicationId = "com.example.tourmate"
```

They must be identical.

---

## 10. Configure the Backend URL

The mobile app communicates with the FastAPI backend via REST API and WebSocket.

### If testing with an emulator

The Android emulator cannot reach `localhost` on your machine — it uses a special IP instead.

Find the config file (likely `lib/core/network/api_services.dart` or `lib/core/constants.dart`) and set:

```dart
// http://10.0.2.2 maps to your PC's localhost inside the emulator
```

### If testing with a physical device

Your phone and PC must be on the **same Wi-Fi network**. Find your PC's local IP:

```powershell
# Windows
ipconfig
# Look for "IPv4 Address" under your Wi-Fi adapter — e.g. 192.168.1.5
```

Then set the base URL to `http://192.168.1.5:8000`.

### If the backend is deployed

Replace with the deployed URL (e.g. `https://api.tourmate.ai`).

---

## 11. Run the App

### Make sure the backend is running first

In a separate terminal:

```bash
cd TourMate-AI/backend
venv\Scripts\Activate.ps1   # Windows
uvicorn app.main:app --reload
```

### Make sure an emulator or device is connected

```bash
flutter devices
# Should list at least one device, e.g.:
# sdk gphone x86 64 (mobile) • emulator-5554 • android-x64 • Android 14
```

### Run the app

From inside the `mobile/` folder:

```bash
flutter run
```

Or from Android Studio: click the green **▶️ Run** button in the toolbar.

First run takes 1–2 minutes to compile. Subsequent runs are much faster.

---

## 12. Run on a Physical Android Device

If you prefer testing on a real phone:

### Step 1 — Enable Developer Options on your phone

1. Go to **Settings → About phone**
2. Tap **Build number** 7 times quickly
3. You'll see: *"You are now a developer!"*

### Step 2 — Enable USB Debugging

1. Go to **Settings → Developer Options**
2. Turn on **USB Debugging**

### Step 3 — Connect via USB

1. Plug your phone into your PC with a USB cable
2. On your phone, tap **Allow** when prompted for USB debugging authorization
3. Verify the device is detected:

```bash
flutter devices
# Your phone should appear in the list
```

### Step 4 — Run

```bash
flutter run
```

---

## 13. Project Structure Overview

The mobile app uses a **feature-first** folder architecture:

```
mobile/
│
├── lib/
│   ├── main.dart                         # App entry point
│   ├── firebase_options.dart             # Firebase config (auto-generated)
│   │
│   ├── app/
│   │   ├── app.dart                      # MaterialApp + providers
│   │   └── app_router.dart               # Route definitions
│   │
│   ├── core/                             # Shared infrastructure
│   │   ├── errors/
│   │   │   ├── api_result.dart           # API result wrapper (freezed)
│   │   │   └── auth_error_handler.dart   # Auth error handling
│   │   ├── layout/
│   │   │   └── main_shell.dart           # Bottom nav shell
│   │   └── network/
│   │       ├── api_services.dart         # Retrofit API client (generated)
│   │       ├── dio_factory.dart          # Dio HTTP client setup
│   │       └── service_locator.dart      # get_it dependency injection
│   │
│   └── features/                         # Feature modules
│       ├── auth/                         # Authentication
│       │   ├── data/
│       │   │   ├── datasource/
│       │   │   │   └── firebase_auth_service.dart
│       │   │   ├── models/
│       │   │   │   ├── register_request.dart
│       │   │   │   ├── user_response.dart
│       │   │   │   └── full_profile_response.dart
│       │   │   └── repository/
│       │   │       ├── auth_repository.dart
│       │   │       └── profile_repository.dart
│       │   ├── logic/
│       │   │   ├── profile_cubit.dart
│       │   │   └── profile_state.dart (+freezed)
│       │   └── presentation/
│       │       ├── screens/
│       │       │   ├── signin_screen.dart
│       │       │   ├── signup_screen.dart
│       │       │   ├── profile_screen.dart
│       │       │   └── quiz_decision_screen.dart
│       │       └── widgets/
│       │           └── custom_textfield.dart
│       │
│       ├── chat/                         # AI Chat interface
│       │   ├── data/
│       │   │   ├── datasource/
│       │   │   │   └── chat_ws_service.dart  # WebSocket client
│       │   │   ├── models/
│       │   │   │   └── chat_message.dart
│       │   │   └── repository/
│       │   │       └── chat_repository.dart
│       │   ├── logic/
│       │   │   ├── chat_cubit.dart
│       │   │   └── chat_state.dart (+freezed)
│       │   └── presentation/
│       │       ├── screens/
│       │       │   └── chat_screen.dart
│       │       └── widgets/
│       │           └── message_bubble.dart
│       │
│       ├── quiz/                         # Onboarding personality quiz (8 screens)
│       │   ├── data/
│       │   │   ├── models/
│       │   │   │   ├── quiz_answers.dart
│       │   │   │   ├── quiz_submit_request.dart
│       │   │   │   └── persona_response.dart
│       │   │   └── repository/
│       │   │       └── quiz_repository.dart
│       │   ├── logic/
│       │   │   ├── quiz_cubit.dart
│       │   │   └── quiz_state.dart (+freezed)
│       │   └── presentation/
│       │       ├── screens/
│       │       │   ├── onboarding_flow.dart
│       │       │   ├── screen1_basics.dart
│       │       │   ├── screen2_vacation.dart
│       │       │   ├── screen3_accommodation.dart
│       │       │   ├── screen4_activities.dart
│       │       │   ├── screen5_dining.dart
│       │       │   ├── screen6_interests.dart
│       │       │   ├── screen7_traveler_type.dart
│       │       │   └── screen8_summary.dart
│       │       └── widgets/
│       │           ├── choice_chip2.dart
│       │           ├── nav_buttons.dart
│       │           ├── quiz_scaffold.dart
│       │           ├── radio_option.dart
│       │           └── slider_toggle.dart
│       │
│       ├── trips/                        # Trip management
│       │   ├── data/
│       │   │   ├── models/
│       │   │   │   ├── trip_summary_model.dart
│       │   │   │   └── create_trip_request.dart
│       │   │   └── repository/
│       │   │       └── trips_repository.dart
│       │   ├── logic/
│       │   │   ├── trips_cubit.dart
│       │   │   └── trips_state.dart (+freezed)
│       │   └── presentation/
│       │       └── screens/
│       │           ├── trips_screen.dart
│       │           └── create_trip_screen.dart
│       │
│       └── splash/                       # Splash / loading screen
│           └── splash_screen.dart
│
├── android/                              # Android native config
│   └── app/
│       ├── build.gradle.kts
│       └── google-services.json          # Firebase config (NOT in Git)
│
├── ios/                                  # iOS native config
│   └── Runner/
│       └── GoogleService-Info.plist      # Firebase config (NOT in Git)
│
├── assets/images/                        # App images and icons
├── pubspec.yaml                          # Flutter dependencies
└── pubspec.lock                          # Locked dependency versions
```

### Feature Module Pattern

Each feature follows the same internal structure:

```
feature/
├── data/
│   ├── datasource/    # Remote/local data sources (API calls, Firebase)
│   ├── models/        # Data models (freezed + json_serializable)
│   └── repository/    # Repository pattern (abstracts data sources)
├── logic/
│   ├── feature_cubit.dart    # State management (flutter_bloc)
│   └── feature_state.dart    # State classes (freezed union types)
└── presentation/
    ├── screens/       # Full-screen widgets
    └── widgets/       # Reusable feature-specific widgets
```

---

## 14. Key Dependencies

| Package | Purpose |
|---------|---------|
| `flutter_bloc` | State management (Cubit pattern) |
| `freezed` + `freezed_annotation` | Immutable data classes with union types |
| `json_serializable` | Automatic JSON serialization |
| `dio` | HTTP client for REST API |
| `retrofit` | Type-safe API client (generates from annotations) |
| `get_it` | Dependency injection / service locator |
| `firebase_core` + `firebase_auth` | Firebase integration |
| `google_sign_in` | Google OAuth sign-in |
| `web_socket_channel` | WebSocket for real-time chat |
| `flutter_secure_storage` | Secure token storage |
| `shared_preferences` | Local key-value storage |

---

## 15. Common Errors & Fixes

---

### ❌ `flutter: command not found`

Flutter is not in your PATH. Re-do Step 2 (add `C:\dev\flutter\bin` to PATH) and open a **new** terminal window.

---

### ❌ `flutter doctor` shows Android toolchain issues

```bash
# Accept licenses
flutter doctor --android-licenses

# If Android SDK is not found, set its path
flutter config --android-sdk "C:\Users\YourName\AppData\Local\Android\Sdk"
```

---

### ❌ `google-services.json not found` / Firebase crashes on startup

The file is missing from `android/app/`. Follow Step 9 to download and place it correctly.

---

### ❌ `CLEARTEXT communication not permitted` (HTTP blocked on Android)

Android 9+ blocks plain HTTP by default. For local development, add this to `android/app/src/main/AndroidManifest.xml`:

```xml
<application
    android:usesCleartextTraffic="true"   ← add this line
    ...>
```

> Only do this for development. The production build should use HTTPS.

---

### ❌ `Connection refused` / API calls fail on emulator

You're using `localhost` or `127.0.0.1` in the base URL. The emulator can't reach these.

Change to:
```dart
// http://10.0.2.2 maps to your PC's localhost inside the emulator
```

---

### ❌ `Gradle build failed` / `SDK location not found`

Android Studio hasn't finished downloading the SDK. Go to:
**Tools → SDK Manager** → confirm Android SDK is installed under the SDK Platforms tab.

Or create `mobile/android/local.properties` manually:

```properties
sdk.dir=C\:\\Users\\YourName\\AppData\\Local\\Android\\Sdk
```

---

### ❌ `A problem occurred evaluating project ':app'` (package name mismatch)

The `package_name` in `google-services.json` doesn't match `applicationId` in `build.gradle.kts`. Make sure both are exactly `com.example.tourmate`.

---

### ❌ `flutter pub get` fails with network error

You might be behind a proxy or firewall. Try:

```bash
flutter pub get --no-precompile
```

Or check if you need to configure pub's proxy settings.

---

### ❌ Emulator is extremely slow

Enable **Hardware Acceleration (HAXM)** in Android Studio:

1. Go to **Tools → SDK Manager → SDK Tools**
2. Check **Android Emulator Hypervisor Driver (AEHD)** or **Intel HAXM**
3. Apply and install

Also make sure virtualization is enabled in your BIOS (VT-x on Intel, AMD-V on AMD).

---

### ❌ `build_runner` / code generation errors

If you see errors about generated files (`.freezed.dart`, `.g.dart`):

```bash
dart run build_runner build --delete-conflicting-outputs
```

---

## 16. Quick-Start Checklist

Use this before asking for help:

- [ ] Flutter SDK installed and `flutter --version` works
- [ ] Android Studio installed with Flutter + Dart plugins
- [ ] `flutter doctor` shows all green (or only optional warnings)
- [ ] Emulator created and running (or physical device connected)
- [ ] Repo cloned and `mobile/` folder opened in Android Studio
- [ ] `flutter pub get` completed without errors
- [ ] `dart run build_runner build --delete-conflicting-outputs` ran successfully
- [ ] `google-services.json` placed in `mobile/android/app/`
- [ ] Base URL configured for your setup (emulator / device / deployed)
- [ ] Backend is running (`uvicorn app.main:app --reload`)
- [ ] `flutter run` launches the app without errors

---

*Last updated: June 2026 — TourMate AI Team*
