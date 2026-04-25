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
14. [Common Errors & Fixes](#14-common-errors--fixes)
15. [Quick-Start Checklist](#15-quick-start-checklist)

---

## 1. Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Android Studio | Hedgehog (2023.1.1) or newer | https://developer.android.com/studio |
| Flutter SDK | 3.19.x or newer | https://docs.flutter.dev/get-started/install |
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
cd TourMate-AI
```

The mobile app lives in the `mobile/` folder (or `flutter_app/` — check the repo structure after cloning).

```bash
cd mobile   # adjust to whatever the folder is named
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
"package_name": "com.tourmate.ai"
```

Open `mobile/android/app/build.gradle` and confirm `applicationId` matches:

```gradle
applicationId "com.tourmate.ai"
```

They must be identical.

---

## 10. Configure the Backend URL

The mobile app needs to know where the FastAPI backend is running.

### If testing with an emulator

The Android emulator cannot reach `localhost` on your machine — it uses a special IP instead.

Find the config file (likely `lib/core/constants.dart` or `lib/config/api_config.dart`) and set:

```dart
const String baseUrl = 'http://10.0.2.2:8000';
//                              ^^^^^^^^^^
//                              This maps to your PC's localhost inside the emulator
```

### If testing with a physical device

Your phone and PC must be on the **same Wi-Fi network**. Find your PC's local IP:

```powershell
# Windows
ipconfig
# Look for "IPv4 Address" under your Wi-Fi adapter — e.g. 192.168.1.5
```

Then set:

```dart
const String baseUrl = 'http://192.168.1.5:8000';
```

### If the backend is deployed

Replace with the deployed URL:

```dart
const String baseUrl = 'https://api.tourmate.ai';
```

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

```
mobile/
│
├── lib/                          # All Dart source code lives here
│   ├── main.dart                 # App entry point
│   │
│   ├── core/                     # Shared utilities
│   │   ├── constants.dart        # Base URL, API keys, app-wide constants
│   │   ├── theme.dart            # Colors, fonts, app theme
│   │   └── router.dart           # Navigation routes (GoRouter / auto_route)
│   │
│   ├── features/                 # Feature-first folder structure
│   │   ├── auth/                 # Login, register, Firebase auth
│   │   │   ├── data/             # API calls and Firebase calls
│   │   │   ├── domain/           # Business logic and models
│   │   │   └── presentation/     # Screens and widgets
│   │   │
│   │   ├── chat/                 # AI chat interface
│   │   ├── trips/                # Trip planning and history
│   │   ├── profile/              # User profile and preferences quiz
│   │   └── home/                 # Home / dashboard screen
│   │
│   └── shared/                   # Reusable widgets used across features
│       ├── widgets/
│       └── services/             # HTTP client, local storage, etc.
│
├── android/                      # Android-specific native config
│   └── app/
│       ├── google-services.json  # Firebase config (NOT in Git — add manually)
│       └── build.gradle          # App-level Gradle config
│
├── assets/                       # Images, fonts, icons, Lottie animations
│
├── pubspec.yaml                  # Flutter dependencies (like requirements.txt)
└── pubspec.lock                  # Locked dependency versions
```

---

## 14. Common Errors & Fixes

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
const String baseUrl = 'http://10.0.2.2:8000';
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

The `package_name` in `google-services.json` doesn't match `applicationId` in `build.gradle`. Make sure both are exactly `com.tourmate.ai`.

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

## 15. Quick-Start Checklist

Use this before asking for help:

- [ ] Flutter SDK installed and `flutter --version` works
- [ ] Android Studio installed with Flutter + Dart plugins
- [ ] `flutter doctor` shows all green (or only optional warnings)
- [ ] Emulator created and running (or physical device connected)
- [ ] Repo cloned and `mobile/` folder opened in Android Studio
- [ ] `flutter pub get` completed without errors
- [ ] `google-services.json` placed in `mobile/android/app/`
- [ ] Base URL set to `http://10.0.2.2:8000` for emulator (or correct IP for device)
- [ ] Backend is running (`uvicorn app.main:app --reload`)
- [ ] `flutter run` launches the app without errors

---

*Last updated: April 2026 — TourMate AI Team*
