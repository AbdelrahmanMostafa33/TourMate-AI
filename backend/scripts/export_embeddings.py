"""Export embeddings from the database to a local JSON file.

Output: data/cairo/cairo_embeddings.json  (place_id → embedding_vector)

Usage (from backend/):
    python scripts/export_embeddings.py

The JSON file is a flat mapping:
    {
        "place_id_1": [0.012, -0.034, ...],
        "place_id_2": [0.098,  0.123, ...],
        ...
    }

This matches the dict format returned by ``load_place_embeddings()``
in ``ai_engine.services.embedding_service``, so the file can be loaded
directly in place of (or as a fallback for) the database call.
"""

import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# ── Paths ────────────────────────────────────────────────────────────────────

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, text          # noqa: E402

DATA_DIR = BACKEND_DIR.parent / "data" / "cairo"
OUTPUT_FILE = DATA_DIR / "cairo_embeddings.json"

# ── Config ───────────────────────────────────────────────────────────────────

_raw_db_url = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:1610@localhost:5432/tourmate",
)
DB_URL = _raw_db_url.replace("+asyncpg", "").replace("+psycopg2", "")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("  Export Embeddings — DB → JSON")
    print("=" * 60)

    # ── 1. Connect ────────────────────────────────────────────────────────────
    print(f"\n[DB] Connecting...")
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("   [OK] Connected")
    except Exception as e:
        print(f"   [FAIL] {e}")
        sys.exit(1)

    # ── 2. Fetch all non-null embeddings ──────────────────────────────────────
    print("\n[DB] Fetching embeddings...")
    query = """
        SELECT place_id, embedding
        FROM places
        WHERE embedding IS NOT NULL
        ORDER BY place_id
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query)).fetchall()

    print(f"   [OK] {len(rows)} embeddings found")

    if not rows:
        print("\n[INFO] No embeddings to export. Run scripts/generate_embeddings.py first.")
        sys.exit(0)

    # ── 3. Build mapping ──────────────────────────────────────────────────────
    embeddings_map: dict[str, list[float]] = {}
    for pid, vec in rows:
        # vec comes back as a JSON list from the DB; normalise to Python list
        if isinstance(vec, str):
            vec = json.loads(vec)
        embeddings_map[pid] = list(vec)

    # ── 4. Ensure output directory exists ─────────────────────────────────────
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── 5. Write JSON ─────────────────────────────────────────────────────────
    print(f"\n[FILE] Writing {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(embeddings_map, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    file_size = OUTPUT_FILE.stat().st_size
    print(f"   [OK] {len(embeddings_map)} embeddings exported ({file_size / 1024 / 1024:.1f} MB)")

    # ── 6. Verify ─────────────────────────────────────────────────────────────
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        reloaded = json.load(f)
    first_key = next(iter(reloaded.keys()), None)
    first_vec = reloaded.get(first_key) if first_key else None
    print(f"\n[VERIFY]")
    print(f"   Entries:     {len(reloaded)}")
    print(f"   Sample key:  {first_key}")
    print(f"   Dimensions:  {len(first_vec) if first_vec else 'N/A'}")
    print(f"   First 3 vals: {first_vec[:3] if first_vec else 'N/A'}...")
    print(f"\n[DONE] Exported to {OUTPUT_FILE.relative_to(BACKEND_DIR.parent)}")


if __name__ == "__main__":
    main()
