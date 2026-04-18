from fastapi import Depends, HTTPException, Header
from app.core.firebase import verify_token

async def get_current_user(authorization: str = Header(...)):

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.split("Bearer ")[1]
    user = verify_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user