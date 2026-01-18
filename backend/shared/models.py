# backend/shared/models.py
"""
Shared Pydantic models used across modules
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class User(BaseModel):
    """User model shared across modules"""
    id: Optional[int] = None
    email: str
    name: str
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class APIResponse(BaseModel):
    """Standard API response format"""
    success: bool
    message: str
    data: Optional[dict] = None