import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.database import engine, Base
from app.models import user, profile, trip, chat

from app.api.v1.routes import auth, users, health
from app.api.v1.routes import trips as trips_router
from app.api.v1.routes import chat  as chat_router
from app.api.v1.routes import reviews as reviews_router
from app.api.v1.routes import saved_places as saved_places_router
from app.api.v1.routes import images as images_router
from app.api.v1.routes import places as places_router
from app.api.v1.routes import itinerary as itinerary_router
from app.api.v1.routes import feedback as feedback_router
from ai_engine.observability.tracing import setup_langsmith


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── إنشاء الـ Tables لما السيرفر يشتغل ───────────────────────────────────
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ── Initialize LangSmith tracing ───────────────────────────────────────
    setup_langsmith()

    yield


app = FastAPI(
    title    = "TourMate AI Backend",
    lifespan = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/api/v1/auth",  tags=["Auth"])
app.include_router(users.router,        prefix="/api/v1/users", tags=["Users"])
app.include_router(trips_router.router, prefix="/api/v1/trips", tags=["Trips"])
app.include_router(chat_router.router,  prefix="/api/v1",       tags=["Chat"])
app.include_router(reviews_router.router, prefix="/api/v1/reviews", tags=["Reviews"])
app.include_router(saved_places_router.router, prefix="/api/v1/saved-places", tags=["Saved Places"])
app.include_router(images_router.router, prefix="/api/v1/images", tags=["Images"])
app.include_router(places_router.router, prefix="/api/v1/places", tags=["Places"])
app.include_router(itinerary_router.router, prefix="/api/v1/itinerary", tags=["Itinerary"])
app.include_router(feedback_router.router, prefix="/api/v1/feedback", tags=["Feedback"])
app.include_router(health.router,       tags=["Health"])


@app.get("/")
def root():
    return {"message": "TourMate Backend Running"}