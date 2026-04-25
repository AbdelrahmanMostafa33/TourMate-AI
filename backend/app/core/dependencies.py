# backend/app/core/dependencies.py

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.itinerary_service import ItineraryService


async def get_itinerary_service(
    session: AsyncSession = Depends(get_db),
) -> ItineraryService:
    return ItineraryService(db_session=session)