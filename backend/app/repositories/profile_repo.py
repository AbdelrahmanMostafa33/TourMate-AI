# app/repositories/profile_repo.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import TripProfile


class ProfileRepo:
    """Repository for trip_profiles table operations."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_by_trip_id(self, trip_id: str) -> TripProfile | None:
        """Fetch a trip profile by trip_id."""
        result = await self.db.execute(
            select(TripProfile).where(TripProfile.trip_id == trip_id)
        )
        return result.scalar_one_or_none()

    async def create(self, trip_id: str, data: dict) -> TripProfile:
        """Create a new trip profile."""
        import uuid

        profile = TripProfile(
            profile_id=str(uuid.uuid4()),
            trip_id=trip_id,
            **data,
        )
        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def update(self, trip_id: str, data: dict) -> TripProfile | None:
        """Update an existing trip profile."""
        profile = await self.get_by_trip_id(trip_id)
        if not profile:
            return None

        for key, value in data.items():
            if hasattr(profile, key) and value is not None:
                setattr(profile, key, value)

        await self.db.commit()
        await self.db.refresh(profile)
        return profile
