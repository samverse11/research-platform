import time
import json
from fastapi import FastAPI, UploadFile, File, Form, Depends
from typing import Optional
import asyncio
from pydantic import BaseModel

from .services import model_service, SummarizeRequest, TranslateRequest, _log
from .utils import extract_text_from_url, extract_text_from_pdf_bytes
from .cache import compute_file_hash, find_cached_summary, save_summary_to_db, save_upload_metadata

from shared.database import get_db
from sqlalchemy.orm import Session

# Import optional auth dependency
import sys
from pathlib import Path
backend_path = Path(__file__).parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from auth.jwt_handler import get_current_user_id


class UrlRequest(BaseModel):
    url: str
    max_length: int = 512
    source_lang: str = "de"
    target_lang: str = "en"


app = FastAPI(
    title="Summarization Module",
    version="2.0.0",
    root_path="/api/summarization"
)


@app.on_event("startup")
async def startup_event():
    print("Starting Summarization Module...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, model_service.load_models)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── SUMMARIZE TEXT ────────────────────────────────────────────────────────────

@app.post("/summarize")
async def summarize_paper(
    request: SummarizeRequest,
    user_id: int = Depends(get_current_user_id)
):
    _log(f"Summarize request received ({len(request.text):,} chars)")
    t0 = time.time()
    result = model_service.summarize(request)
    _log(f"Summarize complete in {time.time() - t0:.1f}s")
    return result


# ── SUMMARIZE FROM URL ────────────────────────────────────────────────────────

@app.post("/summarize_from_url")
async def summarize_from_url(
    request: UrlRequest,
    user_id: int = Depends(get_current_user_id)
):
    _log(f"Summarize from URL: {request.url[:60]}")
    t0 = time.time()
    text = extract_text_from_url(request.url)
    result = model_service.summarize(SummarizeRequest(text=text, max_length=request.max_length))
    _log(f"Summarize from URL complete in {time.time() - t0:.1f}s")
    return result


# ── SUMMARIZE FILE (with caching) ────────────────────────────────────────────

@app.post("/summarize_file")
async def summarize_file(
    file: UploadFile = File(...),
    max_length: int = Form(512),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if not file.filename:
        return {"detail": "No file provided"}

    filename_lower = file.filename.lower()
    if not (file.content_type == "application/pdf" or filename_lower.endswith(".pdf")):
        return {"detail": "Only PDF files are supported"}

    _log(f"File received: {file.filename}")

    pdf_bytes = await file.read()
    _log(f"  PDF size: {len(pdf_bytes) / 1024:.0f} KB")

    # ── Caching check ──
    file_hash = compute_file_hash(pdf_bytes)

    cached = find_cached_summary(db, file_hash, user_id)
    if cached:
        _log(f"  Returning cached result (id={cached.id})")
        sections = {}
        if cached.sections_json:
            try:
                sections = json.loads(cached.sections_json)
            except Exception:
                pass
        return {
            "final_summary": cached.summary_text or "",
            "sections": sections,
            "cached": True,
        }

    # ── Fresh processing ──
    _log("Starting fresh processing pipeline")
    t0 = time.time()

    text = extract_text_from_pdf_bytes(pdf_bytes)
    result = model_service.summarize(SummarizeRequest(text=text, max_length=max_length))

    processing_time = time.time() - t0

    # Save to database
    save_summary_to_db(
        db, user_id,
        paper_title=file.filename.replace(".pdf", ""),
        paper_hash=file_hash,
        original_filename=file.filename,
        summary_text=result.get("final_summary", ""),
        sections=result.get("sections"),
        model_used="groq-llama-3.3-70b",
        processing_time=processing_time,
    )
    save_upload_metadata(
        db, user_id,
        filename=file.filename,
        file_hash=file_hash,
        file_size=len(pdf_bytes),
        extracted_text_length=len(text),
    )

    return result


# ── TRANSLATE ─────────────────────────────────────────────────────────────────

@app.post("/translate")
async def translate_text(
    request: TranslateRequest,
    user_id: int = Depends(get_current_user_id)
):
    _log(f"Translate request ({request.source_lang} -> {request.target_lang}, {len(request.text):,} chars)")
    t0 = time.time()
    translation = model_service.translate(request)
    _log(f"Translate complete in {time.time() - t0:.1f}s")
    return {"translation": translation}


@app.post("/translate_from_url")
async def translate_from_url(
    request: UrlRequest,
    user_id: int = Depends(get_current_user_id)
):
    _log(f"Translate from URL: {request.url[:60]}")
    t0 = time.time()
    text = extract_text_from_url(request.url)
    translation = model_service.translate(
        TranslateRequest(text=text, source_lang=request.source_lang, target_lang=request.target_lang)
    )
    _log(f"Translate from URL complete in {time.time() - t0:.1f}s")
    return {"translation": translation}


# ── TRANSLATE AND SUMMARIZE FILE (with caching) ──────────────────────────────

@app.post("/translate_and_summarize_file")
async def translate_and_summarize_file(
    file: UploadFile = File(...),
    max_length: int = Form(512),
    source_lang: str = Form("de"),
    target_lang: str = Form("en"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if not file.filename:
        return {"detail": "No file provided"}

    filename_lower = file.filename.lower()
    if not (file.content_type == "application/pdf" or filename_lower.endswith(".pdf")):
        return {"detail": "Only PDF files are supported"}

    _log(f"Translate+Summarize file: {file.filename} ({source_lang} -> {target_lang})")

    pdf_bytes = await file.read()
    _log(f"  PDF size: {len(pdf_bytes) / 1024:.0f} KB")

    # ── Caching check ──
    file_hash = compute_file_hash(pdf_bytes)

    cached = find_cached_summary(db, file_hash, user_id)
    if cached and cached.translated_text:
        _log(f"  Returning cached translate+summarize result (id={cached.id})")
        sections = {}
        if cached.sections_json:
            try:
                sections = json.loads(cached.sections_json)
            except Exception:
                pass
        return {
            "translation": cached.translated_text or "",
            "sections": sections,
            "final_summary": cached.summary_text or "",
            "cached": True,
        }

    # ── Fresh processing ──
    _log("Starting fresh processing pipeline")
    t0 = time.time()

    german_text = extract_text_from_pdf_bytes(pdf_bytes)

    _log("  Starting translation pipeline")
    translation = model_service.translate(
        TranslateRequest(text=german_text, source_lang=source_lang, target_lang=target_lang)
    )

    _log("  Starting summarization pipeline")
    summary_data = model_service.summarize(SummarizeRequest(text=translation, max_length=max_length))

    processing_time = time.time() - t0
    _log(f"  Translate+Summarize complete in {processing_time:.1f}s")

    # Save to database
    save_summary_to_db(
        db, user_id,
        paper_title=file.filename.replace(".pdf", ""),
        paper_hash=file_hash,
        original_filename=file.filename,
        summary_text=summary_data.get("final_summary", ""),
        translated_text=translation,
        sections=summary_data.get("sections"),
        detected_language=source_lang,
        target_language=target_lang,
        model_used="groq-llama-3.3-70b",
        processing_time=processing_time,
    )
    save_upload_metadata(
        db, user_id,
        filename=file.filename,
        file_hash=file_hash,
        file_size=len(pdf_bytes),
        extracted_text_length=len(german_text),
    )

    return {
        "translation": translation,
        "sections": summary_data.get("sections", {}),
        "final_summary": summary_data.get("final_summary", "")
    }
