import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.core import firebase
from app.models import user, trip, profile, chat as chat_models
from app.api.v1.routes import auth, users, chat, trips  # ← ضيف trips


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="TourMate AI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,  prefix="/api/v1/auth",  tags=["Auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(trips.router, prefix="/api/v1/trips", tags=["Trips"])   # ← ضيف ده
app.include_router(chat.router,  prefix="/api/v1",       tags=["Chat"])    # ← غيّر لـ /api/v1 بس


@app.get("/")
async def root():
    return {"message": "TourMate Backend Running ✅"}