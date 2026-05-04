# backend/summarization/app/cache.py
"""
Intelligent paper caching — SHA256 hash-based duplicate detection.
"""

import hashlib
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from shared.models import SummaryHistoryDB, UploadedPaperDB


def _log(msg: str):
    print(f"INFO: [CACHE] {msg}", flush=True)


def compute_file_hash(pdf_bytes: bytes) -> str:
    """Compute SHA256 hex digest of PDF bytes."""
    h = hashlib.sha256(pdf_bytes).hexdigest()
    _log(f"File hash generated: {h[:16]}...")
    return h


def find_cached_summary(
    db: Session,
    file_hash: str,
    user_id: Optional[int] = None,
) -> Optional[SummaryHistoryDB]:
    """
    Look for an existing summary with a matching paper_hash.
    If user_id is provided, search that user's records first;
    otherwise search globally.
    """
    _log("Checking database for existing processed paper")

    query = db.query(SummaryHistoryDB).filter(SummaryHistoryDB.paper_hash == file_hash)

    if user_id is not None:
        # Try user-specific first
        row = query.filter(SummaryHistoryDB.user_id == user_id).first()
        if row:
            _log("Matching paper hash found (user-specific)")
            _log("Cached summary retrieved from database")
            _log("Skipping reprocessing")
            return row

    # Global fallback
    row = db.query(SummaryHistoryDB).filter(SummaryHistoryDB.paper_hash == file_hash).first()
    if row:
        _log("Matching paper hash found (global cache)")
        _log("Cached summary retrieved from database")
        _log("Skipping reprocessing")
        return row

    _log("No cached record found")
    return None


def save_summary_to_db(
    db: Session,
    user_id: Optional[int],
    *,
    paper_title: Optional[str] = None,
    paper_hash: Optional[str] = None,
    original_filename: Optional[str] = None,
    summary_text: Optional[str] = None,
    translated_text: Optional[str] = None,
    sections: Optional[dict] = None,
    detected_language: Optional[str] = None,
    target_language: Optional[str] = None,
    model_used: str = "summarization_model_T5",
    processing_time: Optional[float] = None,
) -> Optional[SummaryHistoryDB]:
    """Save a summary result to the database."""
    if user_id is None:
        _log("Anonymous user — summary not saved to database")
        return None

    record = SummaryHistoryDB(
        user_id=user_id,
        paper_title=paper_title or original_filename,
        paper_hash=paper_hash,
        original_filename=original_filename,
        summary_text=summary_text,
        translated_text=translated_text,
        sections_json=json.dumps(sections) if sections else None,
        detected_language=detected_language,
        target_language=target_language,
        model_used=model_used,
        processing_time=processing_time,
        upload_timestamp=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    _log(f"Summary saved to database (id={record.id})")
    return record


def save_upload_metadata(
    db: Session,
    user_id: Optional[int],
    *,
    filename: str,
    file_hash: str,
    file_size: int,
    total_pages: Optional[int] = None,
    extracted_text_length: Optional[int] = None,
) -> Optional[UploadedPaperDB]:
    """Save upload metadata to the database."""
    if user_id is None:
        return None

    record = UploadedPaperDB(
        user_id=user_id,
        filename=filename,
        file_hash=file_hash,
        file_size=file_size,
        total_pages=total_pages,
        extracted_text_length=extracted_text_length,
        upload_date=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    _log(f"Upload metadata saved (file={filename})")
    return record
