# Contributing to TourMate AI

Thank you for considering contributing to TourMate AI! This document provides guidelines for development workflow, code style, testing, and pull requests.

---

## 📋 Table of Contents

1. [Development Workflow](#-development-workflow)
2. [Setting Up for Development](#-setting-up-for-development)
3. [Coding Standards](#-coding-standards)
4. [Testing](#-testing)
5. [Pull Request Guidelines](#-pull-request-guidelines)
6. [Branching Strategy](#-branching-strategy)
7. [Commit Conventions](#-commit-conventions)

---

## 🔄 Development Workflow

1. **Pick an issue** or create one describing what you're working on
2. **Create a feature branch** from `main` (see [Branching Strategy](#-branching-strategy))
3. **Make changes** following the [Coding Standards](#-coding-standards)
4. **Write/update tests** — new features should include tests
5. **Run the test suite** to ensure nothing is broken
6. **Run linters** and fix any warnings
7. **Open a pull request** following the [PR Guidelines](#-pull-request-guidelines)
8. **Address review feedback** — all conversations must be resolved before merge

---

## 🚀 Setting Up for Development

### Backend (FastAPI + Python)

```bash
# Prerequisites: Python 3.11, PostgreSQL 14+, Redis

# 1. Clone and enter the backend directory
git clone https://github.com/AbdooMatrix/TourMate-AI.git
cd TourMate-AI/backend

# 2. Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 3. Install dependencies (including dev tools)
# Note: pyproject.toml is at the project root, so run from there
cd ..
pip install -e '.[dev]'
cd backend

# 4. Set up environment variables
#    See docs/SETUPS/BACKEND_SETUP.md for full instructions
#    Copy .env.example or create .env with required keys

# 5. Run database migrations
alembic upgrade head

# 6. Seed place data (optional)
python seed_places.py cairo

# 7. Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> 📖 For the complete step-by-step backend setup guide (PostgreSQL, Redis, Firebase, .env), see **[docs/SETUPS/BACKEND_SETUP.md](docs/SETUPS/BACKEND_SETUP.md)**.

### Mobile (Flutter)

```bash
# Prerequisites: Flutter SDK 3.19+, Android Studio

# 1. Enter the mobile directory
cd TourMate-AI/mobile

# 2. Install dependencies
flutter pub get

# 3. Generate code (freezed models, Retrofit clients)
dart run build_runner build --delete-conflicting-outputs

# 4. Configure Firebase
#    Place google-services.json in android/app/

# 5. Run the app (emulator or device required)
flutter run
```

> 📖 For the complete step-by-step mobile setup guide (Flutter SDK, Android Studio, emulator), see **[docs/SETUPS/MOBILE_SETUP.md](docs/SETUPS/MOBILE_SETUP.md)**.

---

## 🎨 Coding Standards

### Python (Backend)

The backend uses **ruff** for linting and formatting.

```bash
# Run ruff linter
ruff check .

# Run ruff formatter (auto-format)
ruff format .
```

**Style rules:**
- **Line length:** 120 characters
- **Target:** Python 3.11+
- **Indentation:** 4 spaces (no tabs)
- **Imports:** Grouped by standard library → third-party → local, separated by blank lines
- **Type hints:** Required for all function signatures and public methods
- **Async:** Use `async/await` throughout — the entire backend is async-first (FastAPI + asyncpg)
- **Naming:**
  - `snake_case` for functions, variables, methods
  - `PascalCase` for classes
  - `UPPER_CASE` for constants
- **Docstrings:** Use triple-quoted docstrings for public modules, classes, and functions

**Project conventions to follow:**
- AI engine agents live in `backend/ai_engine/agents/`
- API route handlers live in `backend/app/api/v1/routes/`
- Business logic goes in `backend/app/services/`
- Database queries go in `backend/app/repositories/`
- Pydantic schemas live in `backend/app/schemas/`
- SQLAlchemy models live in `backend/app/models/`
- New database columns require an Alembic migration

### Dart / Flutter (Mobile)

The mobile app uses **flutter_lints** for static analysis.

```bash
# Run the Dart analyzer
dart analyze

# Or via Flutter
flutter analyze
```

**Style rules:**
- Follow the [Dart style guide](https://dart.dev/guides/language/effective-dart/style)
- **Indentation:** 2 spaces
- **Naming:**
  - `lowerCamelCase` for variables, methods, parameters
  - `PascalCase` for classes, enums, type definitions
  - `snake_case` for file names (e.g., `chat_screen.dart`)
  - `SCREAMING_CASE` for constants
- **State management:** Use `flutter_bloc` (Cubit pattern)
- **Immutability:** Use `freezed` for data classes and state unions
- **API clients:** Use `retrofit` + `dio` for type-safe HTTP calls; regenerate after changes with `dart run build_runner build --delete-conflicting-outputs`
- **Dependency injection:** Use `get_it` service locator

**Project conventions:**
- Feature modules follow the structure:
  ```
  feature/
  ├── data/
  │   ├── datasource/    # Remote/local data sources
  │   ├── models/        # Freezed data models
  │   └── repository/    # Repository pattern
  ├── logic/
  │   ├── feature_cubit.dart
  │   └── feature_state.dart  # Freezed union types
  └── presentation/
      ├── screens/
      └── widgets/
  ```
- Shared code goes in `lib/core/` (network, errors, layout, widgets)
- App-level config goes in `lib/app/` (routing, theme, app root)

---

## 🧪 Testing

### Backend Tests (Python + pytest)

```bash
# From the backend/ directory, with the virtual environment activated

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test categories
pytest tests/unit/ -v
pytest tests/unit/test_ai_engine/ -v
pytest tests/integration/ -v

# Run a specific test file
pytest tests/unit/test_ai_engine/test_planning_agent.py -v

# Run with stdout/stderr visible
pytest -v -s

# Stop on first failure
pytest -v -x

# Run with coverage
pip install pytest-cov
pytest --cov=app --cov=ai_engine
```

**Test categories:**

| Category | Location | Count | Purpose |
|----------|----------|-------|---------|
| AI Engine Unit | `tests/unit/test_ai_engine/` | 27 | Individual agent and service tests |
| AI Services Unit | `tests/unit/test_services/` | — | Service layer (Amadeus, booking, auth) |
| API Routes | `tests/unit/test_routes/` | — | FastAPI endpoint tests |
| Integration | `tests/integration/` | 25 | Full pipeline, end-to-end feature flows |
| E2E | `tests/e2e/` | — | Complete user journey scenarios |

### Mobile Tests (Flutter)

```bash
# From the mobile/ directory

# Run all tests
flutter test

# Run a specific test file
flutter test test/unit/chat_ws_service_test.dart

# Run with coverage
flutter test --coverage
```

**Test categories:**

| Category | File(s) | Purpose |
|----------|---------|---------|
| Unit | `test/unit/*_test.dart` | Cubit logic, WebSocket, data processing |
| Widget | `test/widget_test.dart` | UI rendering |

### Writing Tests

**Backend:**
- Test files follow the pattern `test_<module_name>.py`
- Async tests should use `async def` with pytest-asyncio (auto-enabled)
- Use fixtures from `backend/tests/conftest.py` for shared setup (test DB, test client, auth headers)
- Mock external services (Amadeus, Stripe, Gemini, Groq) in unit tests

**Mobile:**
- Use `flutter_test` with `Mockito` for mocking dependencies
- Test Cubit logic independently from UI
- Freezed models should have serialization/deserialization tests

---

## 📤 Pull Request Guidelines

### Before Submitting

- [ ] Code compiles and runs without errors
- [ ] All existing tests pass (`pytest -v` / `flutter test`)
- [ ] New tests added for new functionality
- [ ] Linters pass (`ruff check .` / `flutter analyze`)
- [ ] Code follows the project's naming and style conventions
- [ ] No `print()` / `debugPrint()` statements left in production code
- [ ] Database migrations are included if schema changed
- [ ] Environment variables added to `.env` example (if applicable)
- [ ] Documentation updated (README, setup guides, or API docs) if behavior changed
- [ ] Generated code (freezed, retrofit) is up to date

### PR Title Format

Use conventional commits for PR titles:

```
type(scope): brief description
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `style`, `chore`, `perf`
**Scope examples:** `backend`, `mobile`, `ai-engine`, `api`, `docs`, `ci`

Examples:
- `feat(ai-engine): add multi-city itinerary support`
- `fix(api): handle null response from Amadeus flight search`
- `docs(backend): update setup guide with Stripe env vars`

### PR Description Template

```markdown
## What does this PR do?

Brief description of the change.

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor (no functional changes)
- [ ] Documentation update
- [ ] Test update

## How has this been tested?

Describe the tests you ran.

## Checklist

- [ ] Code compiles
- [ ] All tests pass
- [ ] Linters pass
- [ ] Tests added/updated
- [ ] Docs updated

## Related issues

Closes #...
```

### Review Process

1. All PRs require at least **one approval** from a team member
2. All comments/discussions must be resolved before merging
3. The PR author is responsible for merging after approval
4. Use **Squash and Merge** to keep the git history clean

---

## 🌿 Branching Strategy

```
main (production-ready)
  └── feature/* (new features)
  └── fix/* (bug fixes)
  └── docs/* (documentation only)
  └── refactor/* (code improvements)
```

- **`main`** — Always deployable. Protected — no direct commits.
- **`feature/<name>`** — Branch from `main`, merge back via PR.
- **`fix/<name>`** — Branch from `main` for bug fixes.
- **`docs/<name>`** — Documentation-only changes.
- **`refactor/<name>`** — Code restructuring with no functional changes.

Keep branches short-lived (ideally < 1 week). Rebase on `main` before submitting a PR to resolve conflicts.

---

## 📝 Commit Conventions

Follow [conventional commits](https://www.conventionalcommits.org/) for all commit messages:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Examples:**

```
feat(ai-engine): implement multi-city routing in planning agent

Adds support for generating itineraries that span multiple cities,
with OSRM-based travel time estimation between cities.

Closes #42
```

```
fix(api): handle empty flight search results

Amadeus returns 200 with empty data when no flights are found.
Changed the response to return an empty list instead of 500.

Fixes #87
```

```
docs(backend): add Stripe env vars to setup guide
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

---

<div align="center">

**Thank you for contributing to TourMate AI! 🧳✨**

</div>
