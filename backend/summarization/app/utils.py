# backend/summarization/app/utils.py

import re
import io
import time
import requests
import pymupdf
from fastapi import HTTPException
from typing import List


def _log(msg: str):
    print(f"INFO: {msg}", flush=True)


# -------------------------------
# TEXT EXTRACTION
# -------------------------------

def remove_header_metadata(text: str) -> str:
    if "Abstract" in text:
        return text.split("Abstract", 1)[1]
    return text


def remove_keywords(text: str) -> str:
    return re.sub(
        r"Keywords—.*?Introduction",
        "Introduction",
        text,
        flags=re.DOTALL,
    )


def remove_references(text: str) -> str:
    if "REFERENCES" in text:
        text = text.split("REFERENCES")[0]
    if "References" in text:
        text = text.split("References")[0]
    return text


def remove_section_headings(text: str) -> str:
    return re.sub(r"\b[IVX]+\.\s+[A-Z ]+", "", text)


def clean_text(text: str) -> str:
    text = re.sub(r"-\n", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    t0 = time.time()
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        doc = pymupdf.open(stream=pdf_file, filetype="pdf")
        page_count = len(doc)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found")

    _log(f"  PDF parsed: {page_count} pages | {len(text):,} chars | {time.time() - t0:.2f}s")
    return text


def extract_text_from_url(url: str) -> str:
    if "arxiv.org/abs/" in url:
        url = url.replace("/abs/", "/pdf/") + ".pdf"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch content: {str(e)}")

    content_type = response.headers.get("Content-Type", "").lower()
    text = ""

    if "pdf" in content_type or url.endswith(".pdf"):
        try:
            text = extract_text_from_pdf_bytes(response.content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
    else:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, "html.parser")
            paragraphs = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "li"])
            text = "\n".join(p.get_text() for p in paragraphs)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse HTML: {str(e)}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found")

    return text


# -------------------------------
# CLEANING FUNCTIONS
# -------------------------------

def clean_research_text(text: str) -> str:
    if "REFERENCES" in text:
        text = text.split("REFERENCES")[0]
    if "References" in text:
        text = text.split("References")[0]
    text = re.sub(r'Keywords—.*?Introduction', 'Introduction', text, flags=re.DOTALL)
    text = re.sub(r'\b[IVX]+\.\s+[A-Z ]+', '', text)
    text = re.sub(r'-\n', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# -------------------------------
# SECTION DETECTION
# -------------------------------

def split_into_sections(text: str):
    sections = {
        "abstract": "",
        "method": "",
        "results": "",
        "conclusion": ""
    }

    lower = text.lower()

    markers = {
        "abstract": ["abstract"],
        "method": ["method", "methodology", "proposed method"],
        "results": ["result", "results", "experiment", "evaluation"],
        "conclusion": ["conclusion"]
    }

    for section, keywords in markers.items():
        for k in keywords:
            idx = lower.find(k)
            if idx != -1:
                sections[section] = text[idx: idx + 5000]
                break

    return sections


# -------------------------------
# CHUNKING
# -------------------------------

def intelligent_chunking(text: str, tokenizer, max_tokens: int = 500) -> List[str]:
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    chunks = []
    current_chunk = ""
    current_tokens = 0

    for paragraph in paragraphs:
        p_tokens = len(tokenizer.encode(paragraph))
        if current_tokens + p_tokens > max_tokens:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n"
            current_tokens = p_tokens
        else:
            current_chunk += paragraph + "\n"
            current_tokens += p_tokens

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def chunk_text_with_overlap(text: str, tokenizer, max_tokens: int, overlap_words: int) -> List[str]:
    paragraphs = re.split(r"\n+|\.\s", text)
    chunks: List[str] = []
    current_chunk = ""
    current_tokens = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        tokens = tokenizer.encode(para, add_special_tokens=False)
        length = len(tokens)
        if current_tokens + length <= max_tokens:
            current_chunk = (current_chunk + " " + para).strip()
            current_tokens += length
            continue
        if current_chunk:
            chunks.append(current_chunk.strip())
        overlap = " ".join(current_chunk.split()[-overlap_words:]) if current_chunk else ""
        current_chunk = (overlap + " " + para).strip()
        current_tokens = len(tokenizer.encode(current_chunk, add_special_tokens=False))

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# -------------------------------
# IMPORTANCE FILTERING
# -------------------------------

def score_chunk(chunk: str) -> int:
    keywords = [
        "method", "proposed", "approach", "model",
        "experiment", "result", "accuracy", "dataset",
        "evaluation", "system", "classification", "detection"
    ]
    score = 0
    chunk_lower = chunk.lower()
    for k in keywords:
        if k in chunk_lower:
            score += 1
    return score


def select_important_chunks(chunks, top_ratio=0.6):
    scored = [(chunk, score_chunk(chunk)) for chunk in chunks]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_n = max(1, int(len(chunks) * top_ratio))
    return [c[0] for c in scored[:top_n]]