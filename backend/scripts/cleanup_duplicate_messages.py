"""
Clean up duplicate messages created by a bug in `rebuild_conversation_state_from_db`.

The bug (now fixed) mapped `"agent"` (DB sender) → `"user"` (ChatMessage role)
instead of `"agent"` → `"assistant"`.  This caused `sync_redis_to_db` to see
fingerprint `("user", content)` from the rebuilt Redis state, which didn't
match `("agent", content)` in the DB, so it inserted a NEW message with
`sender="user"` and the exact same content as the original agent message.

This script finds and deletes those bogus user messages.
"""

import asyncio
import sys
import os

# Add backend directory to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select, delete, text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession


async def main():
    # Read DB URL from environment or default
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/tourmate",
    )

    engine = create_async_engine(database_url, echo=False)
    async with AsyncSession(engine) as session:
        # 1. Find duplicate user messages that match an agent message (same conversation, same content)
        find_dupes_sql = sa_text("""
            SELECT m.message_id, m.conversation_id, m.content, m.timestamp
            FROM messages m
            WHERE m.sender = 'user'
              AND EXISTS (
                SELECT 1 FROM messages m2
                WHERE m2.conversation_id = m.conversation_id
                  AND m2.sender = 'agent'
                  AND m2.content = m.content
              )
            ORDER BY m.timestamp ASC
        """)

        result = await session.execute(find_dupes_sql)
        duplicates = result.fetchall()

        if not duplicates:
            print("✅ No duplicate messages found. Database is clean.")
            return

        print(f"🔍 Found {len(duplicates)} duplicate user message(s):")
        for dup in duplicates:
            preview = dup.content[:80] + "..." if len(dup.content) > 80 else dup.content
            print(f"   - [{dup.conversation_id}] \"{preview}\" (msg_id={dup.message_id[:8]}..., timestamp={dup.timestamp})")

        # 2. Delete duplicate user messages
        dupe_ids = [d.message_id for d in duplicates]
        delete_sql = sa_text("""
            DELETE FROM messages
            WHERE message_id = ANY(:msg_ids)
        """)

        await session.execute(delete_sql, {"msg_ids": dupe_ids})
        await session.commit()
        print(f"✅ Deleted {len(duplicates)} duplicate message(s).")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
