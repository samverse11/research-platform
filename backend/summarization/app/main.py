from fastapi import FastAPI, UploadFile, File, Form
import asyncio
from pydantic import BaseModel

from .services import model_service, SummarizeRequest, TranslateRequest
from .utils import extract_text_from_url, extract_text_from_pdf_bytes


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
    print("🚀 Starting Summarization Module...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, model_service.load_models)


@app.get("/health")
async def health():
    return {"status": "ok"}


# -------------------------------
# SUMMARIZE TEXT
# -------------------------------

@app.post("/summarize")
async def summarize_paper(request: SummarizeRequest):
    return model_service.summarize(request)


# -------------------------------
# SUMMARIZE FROM URL
# -------------------------------

@app.post("/summarize_from_url")
async def summarize_from_url(request: UrlRequest):
    text = extract_text_from_url(request.url)
    return model_service.summarize(
        SummarizeRequest(text=text, max_length=request.max_length)
    )

@app.post("/summarize_file")
async def summarize_file(
    file: UploadFile = File(...),
    max_length: int = Form(512),
):
    if not file.filename:
        return {"detail": "No file provided"}

    filename_lower = file.filename.lower()
    if not (file.content_type == "application/pdf" or filename_lower.endswith(".pdf")):
        return {"detail": "Only PDF files are supported"}

    pdf_bytes = await file.read()
    text = extract_text_from_pdf_bytes(pdf_bytes)
    return model_service.summarize(SummarizeRequest(text=text, max_length=max_length))


# -------------------------------
# TRANSLATE
# -------------------------------

@app.post("/translate")
async def translate_text(request: TranslateRequest):
    return {"translation": model_service.translate(request)}

@app.post("/translate_from_url")
async def translate_from_url(request: UrlRequest):
    text = extract_text_from_url(request.url)
    return {"translation": model_service.translate(
        TranslateRequest(text=text, source_lang=request.source_lang, target_lang=request.target_lang)
    )}

@app.post("/translate_and_summarize_file")
async def translate_and_summarize_file(
    file: UploadFile = File(...),
    max_length: int = Form(512),
    source_lang: str = Form("de"),
    target_lang: str = Form("en"),
):
    if not file.filename:
        return {"detail": "No file provided"}

    filename_lower = file.filename.lower()
    if not (file.content_type == "application/pdf" or filename_lower.endswith(".pdf")):
        return {"detail": "Only PDF files are supported"}

    pdf_bytes = await file.read()
    german_text = extract_text_from_pdf_bytes(pdf_bytes)

    translation = model_service.translate(
        TranslateRequest(text=german_text, source_lang=source_lang, target_lang=target_lang)
    )

    summary_data = model_service.summarize(SummarizeRequest(text=translation, max_length=max_length))

    return {
        "translation": translation,
        "sections": summary_data.get("sections", {}),
        "final_summary": summary_data.get("final_summary", "")
    }
