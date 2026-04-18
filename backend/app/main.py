import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.database import engine, Base
from app.models import user, profile, trip, chat

from app.api.v1.routes import auth, users
from app.api.v1.routes import trips as trips_router
from app.api.v1.routes import chat  as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── إنشاء الـ Tables لما السيرفر يشتغل ───────────────────────────────────
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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


@app.get("/")
def root():
    return {"message": "TourMate Backend Running"}