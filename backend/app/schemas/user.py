from pydantic import BaseModel, EmailStr
from typing import Optional


class RegisterRequest(BaseModel):
    full_name: str
    phone: Optional[str] = None


class UserResponse(BaseModel):
    user_id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    is_active: bool
    role: str = "user"
    class Config:
        from_attributes = True