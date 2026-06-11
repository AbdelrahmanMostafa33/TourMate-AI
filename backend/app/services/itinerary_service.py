# backend/app/services/itinerary_service.py

from ai_engine import handle_chat
from app.repositories.itinerary_repo import ItineraryRepo
from app.repositories.profile_repo import ProfileRepo


class ItineraryService:
    def __init__(self, db_session, redis_client=None):
        self.itinerary_repo = ItineraryRepo(db_session)
        self.profile_repo = ProfileRepo(db_session)
        self.redis = redis_client

    async def generate_trip(self, user_id: str, message: str, images: list = None):
        profile = await self.profile_repo.get_by_user_id(user_id)
        result = await handle_chat(
            user_id=user_id,
            user_message=message,
            image_bytes=images,
            token=None,
        )
        itinerary = await self.itinerary_repo.create(user_id=user_id, data=result)
        return itinerary