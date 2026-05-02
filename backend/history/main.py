# backend/history/main.py
"""
User history / dashboard sub-application — mounted at /api/history
All endpoints require JWT authentication and filter by user_id.
"""

import json
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from shared.database import get_db
from shared.models import (
    SummaryHistoryDB, SearchHistoryDB, UploadedPaperDB,
    SummaryHistoryResponse, SearchHistoryResponse, UploadedPaperResponse,
    DashboardStats,
)
from auth.jwt_handler import get_current_user_id


def _log(msg: str):
    print(f"INFO: [HISTORY] {msg}", flush=True)


app = FastAPI(title="History Module", root_path="/api/history")


# ── Dashboard Stats ───────────────────────────────────────────────────────────

@app.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    total_summaries = db.query(SummaryHistoryDB).filter(SummaryHistoryDB.user_id == user_id).count()
    total_searches = db.query(SearchHistoryDB).filter(SearchHistoryDB.user_id == user_id).count()
    total_uploads = db.query(UploadedPaperDB).filter(UploadedPaperDB.user_id == user_id).count()

    recent_summaries = (
        db.query(SummaryHistoryDB)
        .filter(SummaryHistoryDB.user_id == user_id)
        .order_by(desc(SummaryHistoryDB.created_at))
        .limit(5)
        .all()
    )
    recent_searches = (
        db.query(SearchHistoryDB)
        .filter(SearchHistoryDB.user_id == user_id)
        .order_by(desc(SearchHistoryDB.searched_at))
        .limit(5)
        .all()
    )

    _log(f"Dashboard stats for user {user_id}: {total_summaries}S {total_searches}Q {total_uploads}U")

    return DashboardStats(
        total_summaries=total_summaries,
        total_searches=total_searches,
        total_uploads=total_uploads,
        recent_summaries=[SummaryHistoryResponse.model_validate(s) for s in recent_summaries],
        recent_searches=[SearchHistoryResponse.model_validate(s) for s in recent_searches],
    )


# ── Summaries ─────────────────────────────────────────────────────────────────

@app.get("/summaries")
def list_summaries(
    skip: int = 0,
    limit: int = 50,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(SummaryHistoryDB)
        .filter(SummaryHistoryDB.user_id == user_id)
        .order_by(desc(SummaryHistoryDB.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(SummaryHistoryDB).filter(SummaryHistoryDB.user_id == user_id).count()
    return {
        "items": [SummaryHistoryResponse.model_validate(r) for r in rows],
        "total": total,
    }


@app.get("/summaries/{summary_id}", response_model=SummaryHistoryResponse)
def get_summary(
    summary_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SummaryHistoryDB)
        .filter(SummaryHistoryDB.id == summary_id, SummaryHistoryDB.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Summary not found")
    return SummaryHistoryResponse.model_validate(row)


@app.delete("/summaries/{summary_id}")
def delete_summary(
    summary_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SummaryHistoryDB)
        .filter(SummaryHistoryDB.id == summary_id, SummaryHistoryDB.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Summary not found")
    db.delete(row)
    db.commit()
    _log(f"Summary {summary_id} deleted by user {user_id}")
    return {"success": True, "message": "Summary deleted"}


@app.get("/summaries/{summary_id}/download")
def download_summary(
    summary_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SummaryHistoryDB)
        .filter(SummaryHistoryDB.id == summary_id, SummaryHistoryDB.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Summary not found")

    parts = []
    parts.append(f"Paper: {row.paper_title or row.original_filename or 'Unknown'}")
    parts.append(f"Date: {row.created_at}")
    parts.append(f"Model: {row.model_used or 'N/A'}")
    if row.processing_time:
        parts.append(f"Processing Time: {row.processing_time:.1f}s")
    parts.append("")
    parts.append("=" * 60)
    parts.append("SUMMARY")
    parts.append("=" * 60)
    parts.append(row.summary_text or "No summary available")

    if row.sections_json:
        try:
            sections = json.loads(row.sections_json)
            parts.append("")
            parts.append("=" * 60)
            parts.append("SECTION SUMMARIES")
            parts.append("=" * 60)
            for name, text in sections.items():
                parts.append(f"\n--- {name.upper()} ---")
                parts.append(text)
        except Exception:
            pass

    if row.translated_text:
        parts.append("")
        parts.append("=" * 60)
        parts.append("TRANSLATION")
        parts.append("=" * 60)
        parts.append(row.translated_text)

    content = "\n".join(parts)
    filename = (row.original_filename or "summary").replace(".pdf", "") + "_summary.txt"

    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Search History ────────────────────────────────────────────────────────────

@app.get("/searches")
def list_searches(
    skip: int = 0,
    limit: int = 50,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(SearchHistoryDB)
        .filter(SearchHistoryDB.user_id == user_id)
        .order_by(desc(SearchHistoryDB.searched_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(SearchHistoryDB).filter(SearchHistoryDB.user_id == user_id).count()
    return {
        "items": [SearchHistoryResponse.model_validate(r) for r in rows],
        "total": total,
    }


@app.delete("/searches/{search_id}")
def delete_search(
    search_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SearchHistoryDB)
        .filter(SearchHistoryDB.id == search_id, SearchHistoryDB.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Search record not found")
    db.delete(row)
    db.commit()
    _log(f"Search {search_id} deleted by user {user_id}")
    return {"success": True, "message": "Search record deleted"}


# ── Uploads ───────────────────────────────────────────────────────────────────

@app.get("/uploads")
def list_uploads(
    skip: int = 0,
    limit: int = 50,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UploadedPaperDB)
        .filter(UploadedPaperDB.user_id == user_id)
        .order_by(desc(UploadedPaperDB.upload_date))
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(UploadedPaperDB).filter(UploadedPaperDB.user_id == user_id).count()
    return {
        "items": [UploadedPaperResponse.model_validate(r) for r in rows],
        "total": total,
    }


@app.delete("/uploads/{upload_id}")
def delete_upload(
    upload_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    row = (
        db.query(UploadedPaperDB)
        .filter(UploadedPaperDB.id == upload_id, UploadedPaperDB.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Upload record not found")
    db.delete(row)
    db.commit()
    _log(f"Upload {upload_id} deleted by user {user_id}")
    return {"success": True, "message": "Upload record deleted"}


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "module": "history"}
