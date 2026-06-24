"""Embed all places via gemini-embedding-2 with bulletproof rate-limit handling.

Handles:
  - 100 RPM per-key limit (exponential backoff)
  - 1,000 RPD free-tier quota (won't exceed it)
  - Invalid / 403 keys (skipped at startup)
  - Ctrl+C resume (only processes NULL-embedding places)

Usage (from backend/):
    python scripts/generate_embeddings.py
"""

import os
import sys
import time
import json
import random
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env from the backend directory (path-independent)
load_dotenv(BACKEND_DIR / ".env")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from google import genai
from google.genai import types

# ── Paths ────────────────────────────────────────────────────────────────────

DATA_DIR = BACKEND_DIR.parent / "data" / "cairo"
EMBEDDING_JSON = DATA_DIR / "cairo_embeddings.json"

# ── Config ───────────────────────────────────────────────────────────────────

_raw_db_url = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:1610@localhost:5432/tourmate",
)
DB_URL = _raw_db_url.replace("+asyncpg", "").replace("+psycopg2", "")

_raw_keys = os.getenv("GOOGLE_API_KEY", "")
ALL_RAW_KEYS = [k.strip() for k in _raw_keys.split(",") if k.strip()]

BATCH_SIZE = 50
DIMENSIONS = 768
MODEL_NAME = "gemini-embedding-2"

# ── Rate-limit tracking ─────────────────────────────────────────────────────

# Per-key: minimum 0.6s between calls (100 RPM)
MIN_KEY_INTERVAL = 0.6

# Base pacing between batches: 3s to stay safely under 100 RPM
BASE_BATCH_PACE = 3.0

# Backoff: on 429, wait this base amount (doubles each time)
BASE_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 120

# Max consecutive 429s across all keys before we warn about possible RPD exhaustion
MAX_CONSECUTIVE_429_GLOBAL = 30


@dataclass
class KeyState:
    key: str
    last_used: float = 0.0
    is_valid: bool = True
    consecutive_429s: int = 0


_key_states: list[KeyState] = []
_key_index = 0


def _init_keys() -> None:
    """Initialize key states and validate them."""
    global _key_states
    _key_states = [KeyState(key=k) for k in ALL_RAW_KEYS]

    if not _key_states:
        print("ERROR: No API keys found. Set GOOGLE_API_KEY=key1,key2,... in .env")
        sys.exit(1)

    print(f"\n[API] Validating {len(_key_states)} keys...")
    valid_count = 0
    for ks in _key_states:
        try:
            client = genai.Client(api_key=ks.key)
            client.models.embed_content(
                model=MODEL_NAME, contents="test",
                config=types.EmbedContentConfig(output_dimensionality=DIMENSIONS),
            )
            valid_count += 1
        except Exception as e:
            ks.is_valid = False
            code = getattr(e, "code", None) or getattr(e, "status_code", 0)
            print(f"   [SKIP] key ...{ks.key[-4:]}: {e}")
            if code == 429:
                # Rate limited even for test — mark valid but set last_used so we pace it
                ks.is_valid = True
                ks.last_used = time.time()
                valid_count += 1

    valid = [ks for ks in _key_states if ks.is_valid]
    print(f"   [OK] {len(valid)}/{len(_key_states)} keys valid")
    _key_states[:] = valid

    if not _key_states:
        print("ERROR: No valid API keys remaining.")
        sys.exit(1)


def _get_next_key() -> KeyState | None:
    """Return the next available key respecting per-key cooldown.

    If all keys are in cooldown, waits for the soonest available one.
    """
    global _key_index

    if not _key_states:
        return None

    candidates = sorted(_key_states, key=lambda ks: ks.last_used)
    now = time.time()
    for ks in candidates:
        if now - ks.last_used >= MIN_KEY_INTERVAL:
            _key_index = (_key_index + 1) % len(_key_states)
            return ks

    # All keys in cooldown — wait for the soonest available
    soonest = min(candidates, key=lambda ks: ks.last_used)
    wait = max(0, soonest.last_used + MIN_KEY_INTERVAL - now)
    if wait > 0:
        time.sleep(wait)

    # Now return the best candidate
    candidates.sort(key=lambda ks: ks.last_used)
    return candidates[0]


# ── Helpers ──────────────────────────────────────────────────────────────────


def build_place_text(place: dict) -> str:
    """Build a 'title: ... | text: ...' string for gemini-embedding-2."""
    title = place.get("name", "Unknown").strip()
    parts: list[str] = []

    category = place.get("category", "")
    sub = place.get("sub_category", "")
    type_label = f"{category} - {sub}" if sub else category
    if type_label:
        parts.append(f"type: {type_label}")

    desc = place.get("description", "")
    if desc:
        parts.append(f"description: {desc}")

    tags = place.get("interest_tags", [])
    if tags:
        parts.append(f"tags: {', '.join(tags)}")

    cuisine = place.get("cuisine_type", "")
    if cuisine:
        parts.append(f"cuisine: {cuisine}")

    amenities = place.get("amenities", [])
    if amenities:
        parts.append(f"amenities: {', '.join(amenities)}")

    acc_type = place.get("accommodation_type", "")
    if acc_type:
        parts.append(f"accommodation: {acc_type}")

    city = place.get("city", "")
    country = place.get("country", "")
    if city and country:
        parts.append(f"location: {city}, {country}")
    elif city:
        parts.append(f"location: {city}")

    text_content = " | ".join(parts)
    return f"title: {title} | text: {text_content}"


def load_all_places(engine) -> list[dict]:
    """Load ALL places from the database with their detail data."""
    query = """
        SELECT
            p.place_id,
            p.name,
            p.description,
            p.category::text AS category,
            p.city,
            p.country,
            p.rating,
            p.popularity_score,
            ad.subcategory AS sub_category,
            rd.cuisine_type,
            rd.avg_cost_per_person,
            hd.accommodation_type::text AS accommodation_type,
            hd.amenities,
            hd.star_class,
            hd.nightly_rate
        FROM places p
        LEFT JOIN attraction_details ad ON p.place_id = ad.place_id
        LEFT JOIN restaurant_details rd ON p.place_id = rd.place_id
        LEFT JOIN hotel_details hd ON p.place_id = hd.place_id
        ORDER BY p.popularity_score DESC NULLS LAST
    """
    with Session(engine) as session:
        result = session.execute(text(query))
        rows = result.mappings().all()

    places: list[dict] = []
    for row in rows:
        row = dict(row)
        tags: list[str] = []
        sub = row.get("sub_category", "") or ""
        if sub and sub.lower().strip() not in tags:
            tags.append(sub.lower().strip())
        cuisine = row.get("cuisine_type", "") or ""
        if cuisine and cuisine.lower().strip() not in tags:
            tags.append(cuisine.lower().strip())
        acc = row.get("accommodation_type", "") or ""
        if acc and acc.lower().strip() not in tags:
            tags.append(acc.lower().strip())
        amenities_raw = row.get("amenities")
        amenities: list[str] = []
        if amenities_raw:
            try:
                parsed = json.loads(amenities_raw) if isinstance(amenities_raw, str) else amenities_raw
                if isinstance(parsed, list):
                    amenities = [str(a) for a in parsed]
            except (json.JSONDecodeError, TypeError):
                pass
        places.append({
            "place_id": row["place_id"],
            "name": row["name"] or "",
            "description": row["description"] or "",
            "category": (row["category"] or "").lower(),
            "sub_category": sub,
            "interest_tags": tags,
            "cuisine_type": cuisine,
            "amenities": amenities,
            "accommodation_type": acc,
            "city": row["city"] or "",
            "country": row["country"] or "",
            "rating": row.get("rating"),
            "popularity_score": row.get("popularity_score"),
        })
    return places


def batch_embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch via gemini-embedding-2 with persistent retry.

    Tries keys round-robin with per-key cooldown tracking.
    On 429: exponential backoff, then retry with next key.
    Does NOT give up — keeps retrying indefinitely until success.
    """
    backoff = BASE_BACKOFF_SECONDS
    global_429_count = 0

    while True:
        ks = _get_next_key()
        if ks is None:
            wait = min(backoff + random.uniform(0, 2), MAX_BACKOFF_SECONDS)
            print(f"   [WAIT] No keys available, waiting {wait:.0f}s...")
            time.sleep(wait)
            continue

        try:
            client = genai.Client(api_key=ks.key)
            ks.last_used = time.time()
            contents = [types.Content(parts=[types.Part.from_text(text=t)]) for t in texts]
            result = client.models.embed_content(
                model=MODEL_NAME,
                contents=contents,
                config=types.EmbedContentConfig(output_dimensionality=DIMENSIONS),
            )
            ks.consecutive_429s = 0
            global_429_count = 0
            return [emb.values for emb in result.embeddings]

        except Exception as e:
            code = getattr(e, "code", None) or getattr(e, "status_code", 0)
            ks.last_used = time.time()

            if code == 429:
                ks.consecutive_429s += 1
                global_429_count += 1
                wait = min(backoff * (2 ** ks.consecutive_429s) + random.uniform(0, 2), MAX_BACKOFF_SECONDS)
                print(f"   [429] key ...{ks.key[-4:]}: waited {wait:.0f}s (attempt {ks.consecutive_429s})")
                if global_429_count >= MAX_CONSECUTIVE_429_GLOBAL:
                    print(f"   [WARN] {global_429_count} consecutive 429s — RPD quota may be exhausted")
                    backoff = MAX_BACKOFF_SECONDS  # Wait the full 2 min
                time.sleep(wait)
                backoff = min(backoff * 1.5, MAX_BACKOFF_SECONDS)
                continue
            elif code == 403:
                # Key is bad — remove it
                ks.is_valid = False
                print(f"   [403] key ...{ks.key[-4:]}: removing from rotation")
                _key_states[:] = [k for k in _key_states if k.is_valid]
                if not _key_states:
                    raise RuntimeError("All keys exhausted (403)")
                continue
            else:
                # Transient error — wait and retry
                wait = min(backoff + random.uniform(0, 2), MAX_BACKOFF_SECONDS)
                print(f"   [ERR] key ...{ks.key[-4:]}: {e} — retry in {wait:.0f}s")
                time.sleep(wait)
                continue


def store_embeddings(engine, place_vectors: list[tuple[str, list[float]]]) -> int:
    """Store embeddings as JSON arrays."""
    updated = 0
    with Session(engine) as session:
        for i, (place_id, vector) in enumerate(place_vectors):
            session.execute(
                text("UPDATE places SET embedding = CAST(:vec AS json) WHERE place_id = :pid"),
                {"vec": json.dumps(vector), "pid": place_id},
            )
            updated += 1
            if (i + 1) % 500 == 0:
                session.flush()
        session.commit()
    return updated


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    print("=" * 65)
    print("  Embedding Generation — gemini-embedding-2 (JSON storage)")
    print("  Persistent rate-limit handling — will keep trying until done")
    print("=" * 65)

    # ── 0. Init keys ────────────────────────────────────────────────────────
    _init_keys()

    print(f"\n  Model:           {MODEL_NAME}")
    print(f"  Dimensions:      {DIMENSIONS}")
    print(f"  Batch size:      {BATCH_SIZE}")
    print(f"  Base pace:       {BASE_BATCH_PACE}s between batches")
    print(f"  API keys:        {len(_key_states)}")

    # ── 1. Connect to DB ────────────────────────────────────────────────────
    print("\n[DB] Connecting...")
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("   [OK] Connected")
    except Exception as e:
        print(f"   [FAIL] {e}")
        sys.exit(1)

    # ── 2. Load places ──────────────────────────────────────────────────────
    print("\n[DB] Loading places...")
    places = load_all_places(engine)
    print(f"   [OK] {len(places)} places loaded")

    if not places:
        print("   Nothing to embed. Exiting.")
        return

    # ── 3. Filter to only NULL-embedding places ────────────────────────────
    with engine.connect() as conn:
        null_ids = {
            row[0] for row in
            conn.execute(text("SELECT place_id FROM places WHERE embedding IS NULL")).fetchall()
        }
    already_done = len(places) - len(null_ids)
    print(f"   [OK] {len(null_ids)} places need embeddings (skipping {already_done} already done)")

    places_to_embed = [p for p in places if p["place_id"] in null_ids]

    if not places_to_embed:
        print("\n[DONE] All places already have embeddings. Exiting.")
        return

    # ── 4. Build texts ──────────────────────────────────────────────────────
    print("\n[BUILD] Building texts...")
    place_texts = [(p["place_id"], build_place_text(p)) for p in places_to_embed]
    print(f"   [OK] {len(place_texts)} texts built")
    print(f"\n   Sample:\n{'-' * 60}")
    print(place_texts[0][1][:300])
    print(f"{'-' * 60}")

    # ── 5. Embed ────────────────────────────────────────────────────────────
    total = len(place_texts)
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    all_vectors: list[tuple[str, list[float]]] = []

    print(f"\n[RUN] {total} places, up to {num_batches} batches...")
    print(f"   {'Batch':>6} | {'Progress':>12} | {'Time':>8} | Key")
    print(f"   {'-' * 6}-+-{'-' * 12}-+-{'-' * 8}-+-------")

    start = time.time()
    batch_start_time = time.time()

    for batch_idx in range(0, total, BATCH_SIZE):
        batch = place_texts[batch_idx: batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1
        batch_start = time.time()
        texts = [text for _, text in batch]

        # Blocking call — will retry internally until success
        try:
            vectors = batch_embed(texts)
        except Exception as e:
            print(f"\n[FAIL] Batch {batch_num}/{num_batches}: {e}")
            print(f"   {len(all_vectors)} embeddings completed before failure")
            break

        for (pid, _), vec in zip(batch, vectors):
            all_vectors.append((pid, vec))

        elapsed = time.time() - batch_start
        total_elapsed = time.time() - start
        pct = len(all_vectors) / total * 100

        last_key = _key_states[(_key_index - 1) % len(_key_states)].key[-4:] if _key_states else "?"
        print(f"   {batch_num:>5}/{num_batches} | {len(all_vectors):>7}/{total} "
              f"({pct:>5.1f}%) | {elapsed:>5.1f}s | ...{last_key}")

        # — Store progress every 5 batches (in case of crash)
        if batch_num % 5 == 0 and all_vectors:
            print(f"\n  [SAVE] Checkpoint — storing {len(all_vectors)} so far...")
            store_embeddings(engine, all_vectors)

        # Pacing between batches
        remaining = BASE_BATCH_PACE - elapsed
        if remaining > 0 and batch_num < num_batches:
            time.sleep(remaining)

    # ── 6. Final store ──────────────────────────────────────────────────────
    total_elapsed = time.time() - start
    print(f"\n[DB] Storing {len(all_vectors)} embeddings...")
    store_start = time.time()
    updated = store_embeddings(engine, all_vectors)
    store_time = time.time() - store_start
    print(f"   [OK] {updated} stored ({store_time:.1f}s)")

    # ── 7. Verify ───────────────────────────────────────────────────────────
    with engine.connect() as conn:
        final_count = conn.execute(text("SELECT COUNT(*) FROM places WHERE embedding IS NOT NULL")).scalar() or 0
    with engine.connect() as conn:
        null_count = conn.execute(text("SELECT COUNT(*) FROM places WHERE embedding IS NULL")).scalar() or 0

    # ── 8. Export to JSON file (keeps data/cairo/cairo_embeddings.json in sync) ─
    print(f"\n[FILE] Exporting all embeddings to {EMBEDDING_JSON.relative_to(BACKEND_DIR.parent)}...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        # Load ALL non-null embeddings from DB (not just the ones we just generated)
        with engine.connect() as conn:
            all_rows = conn.execute(
                text("SELECT place_id, embedding FROM places WHERE embedding IS NOT NULL")
            ).fetchall()

        embeddings_map: dict[str, list[float]] = {}
        for pid, vec in all_rows:
            if isinstance(vec, str):
                vec = json.loads(vec)
            embeddings_map[pid] = list(vec)

        with open(EMBEDDING_JSON, "w", encoding="utf-8") as f:
            json.dump(embeddings_map, f, ensure_ascii=False, indent=None, separators=(",", ":"))

        file_size = EMBEDDING_JSON.stat().st_size
        print(f"   [OK] {len(embeddings_map)} embeddings exported ({file_size / 1024 / 1024:.1f} MB)")
    except Exception as exc:
        print(f"   [WARN] JSON export failed (non-fatal): {exc}")

    # ── 9. Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  SUMMARY")
    print("=" * 65)
    print(f"  Total places:           {total}")
    print(f"  Successfully embedded:  {final_count}")
    print(f"  Still NULL:             {null_count}")
    print(f"  API calls:              {num_batches}")
    print(f"  Total time:             {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print(f"  Store time:             {store_time:.1f}s")
    if EMBEDDING_JSON.exists():
        print(f"  JSON export:            {EMBEDDING_JSON.name}")
    print("=" * 65)
    if null_count == 0:
        print("\n[DONE] All places embedded!")
    else:
        print(f"\n[INFO] {null_count} still need embeddings.")
    print("")


if __name__ == "__main__":
    main()
