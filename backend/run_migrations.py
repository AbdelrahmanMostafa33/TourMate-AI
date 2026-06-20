"""Run alembic migrations programmatically."""
import os
import sys

# Ensure we're in the backend directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from alembic.config import Config
from alembic import command

def run():
    alembic_cfg = Config("alembic.ini")
    
    # Ensure DATABASE_URL is set
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        # Normalize to sync driver for Alembic
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql://")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    
    print("=" * 60)
    print("ALEMBIC MIGRATION STATUS")
    print("=" * 60)
    
    # Show current state
    print("\n--- Current Migration State ---")
    command.current(alembic_cfg)
    
    # Show history
    print("\n--- Migration History ---")
    command.history(alembic_cfg)
    
    # Run upgrade
    print("\n--- Running 'upgrade head' ---")
    try:
        command.upgrade(alembic_cfg, "head")
        print("\n✅ All migrations applied successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
    
    # Show final state
    print("\n--- Final Migration State ---")
    command.current(alembic_cfg)

if __name__ == "__main__":
    run()
