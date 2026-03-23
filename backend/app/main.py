from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.core import firebase
from app.models import user, trip
from app.api.v1.routes import auth

Base.metadata.create_all(bind=engine)

app = FastAPI(title="TourMate AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

@app.get("/")
def root():
    return {"message": "TourMate Backend Running ✅"}