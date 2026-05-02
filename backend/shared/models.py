# backend/shared/models.py
"""
SQLAlchemy ORM models  +  Pydantic schemas
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from pydantic import BaseModel, EmailStr

from shared.database import Base


# ═══════════════════════════════════════════════════════════════════════════════
# SQLAlchemy ORM Models
# ═══════════════════════════════════════════════════════════════════════════════

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    profile_image = Column(String(500), nullable=True)

    # relationships
    summaries = relationship("SummaryHistoryDB", back_populates="user", cascade="all, delete-orphan")
    searches = relationship("SearchHistoryDB", back_populates="user", cascade="all, delete-orphan")
    uploads = relationship("UploadedPaperDB", back_populates="user", cascade="all, delete-orphan")


class SummaryHistoryDB(Base):
    __tablename__ = "summary_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    paper_title = Column(String(500), nullable=True)
    paper_hash = Column(String(64), nullable=True, index=True)
    paper_doi = Column(String(255), nullable=True)
    original_filename = Column(String(500), nullable=True)
    summary_text = Column(Text, nullable=True)
    translated_text = Column(Text, nullable=True)
    sections_json = Column(Text, nullable=True)  # JSON-serialized section summaries
    detected_language = Column(String(10), nullable=True)
    target_language = Column(String(10), nullable=True)
    model_used = Column(String(100), nullable=True, default="groq-llama-3.3-70b")
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    processing_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("UserDB", back_populates="summaries")

    __table_args__ = (
        Index("ix_summary_paper_hash", "paper_hash"),
        Index("ix_summary_user_created", "user_id", "created_at"),
    )


class SearchHistoryDB(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    search_query = Column(String(1000), nullable=False)
    results_count = Column(Integer, nullable=True)
    sources_used = Column(String(500), nullable=True)
    searched_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("UserDB", back_populates="searches")


class UploadedPaperDB(Base):
    __tablename__ = "uploaded_papers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    file_size = Column(Integer, nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    total_pages = Column(Integer, nullable=True)
    extracted_text_length = Column(Integer, nullable=True)

    user = relationship("UserDB", back_populates="uploads")

    __table_args__ = (
        Index("ix_upload_file_hash", "file_hash"),
        Index("ix_upload_user_date", "user_id", "upload_date"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Schemas (API validation)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Auth ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    profile_image: Optional[str] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── History ───────────────────────────────────────────────────────────────────

class SummaryHistoryResponse(BaseModel):
    id: int
    paper_title: Optional[str] = None
    paper_hash: Optional[str] = None
    paper_doi: Optional[str] = None
    original_filename: Optional[str] = None
    summary_text: Optional[str] = None
    translated_text: Optional[str] = None
    sections_json: Optional[str] = None
    detected_language: Optional[str] = None
    target_language: Optional[str] = None
    model_used: Optional[str] = None
    processing_time: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SearchHistoryResponse(BaseModel):
    id: int
    search_query: str
    results_count: Optional[int] = None
    sources_used: Optional[str] = None
    searched_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UploadedPaperResponse(BaseModel):
    id: int
    filename: str
    file_hash: str
    file_size: Optional[int] = None
    upload_date: Optional[datetime] = None
    total_pages: Optional[int] = None
    extracted_text_length: Optional[int] = None

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_summaries: int
    total_searches: int
    total_uploads: int
    recent_summaries: List[SummaryHistoryResponse] = []
    recent_searches: List[SearchHistoryResponse] = []


class APIResponse(BaseModel):
    """Standard API response format"""
    success: bool
    message: str
    data: Optional[dict] = None