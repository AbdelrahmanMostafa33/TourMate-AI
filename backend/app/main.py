from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine

from app.models import user, trip

# بيعمل الجداول في الـ Database
Base.metadata.create_all(bind=engine)

app = FastAPI(title="TourMate AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "TourMate Backend Running ✅"}