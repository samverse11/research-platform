import os
import time
import torch
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from dotenv import load_dotenv
from .research_summarizer import summarize_text

from .utils import (
    intelligent_chunking,
    clean_research_text,
    remove_header_metadata,
    remove_keywords,
    remove_references,
    remove_section_headings,
    clean_text,
    split_into_sections,
    chunk_text_with_overlap,
)

load_dotenv()

SUMMARIZATION_MODEL = os.getenv("SUMMARIZATION_MODEL", "summarization_model_T5")
MAX_CHUNK_CHARS = 6000


def _log(msg: str):
    print(f"INFO: {msg}", flush=True)


class SummarizeRequest(BaseModel):
    text: str
    max_length: int = 512


class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "de"
    target_lang: str = "en"


class ModelService:

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.translator_tokenizer = None
        self.translator_model = None

    def load_models(self):
        _log("=" * 60)
        _log("  Loading Summarization & Translation Models")
        _log("=" * 60)

        t0 = time.time()
        self.translator_tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-de-en")
        self.translator_model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-de-en").to(self.device)
        _log(f"  Translation model loaded in {time.time() - t0:.1f}s (Helsinki-NLP/opus-mt-de-en)")

        _log("  Summarization model configured")

        _log("  All models loaded")

    # ── TRANSLATE ─────────────────────────────────────────────────────────────
    def translate(self, request: TranslateRequest) -> str:
        t_start = time.time()
        _log(f"Step 1: Chunking text for translation ({len(request.text):,} chars)")

        chunks = intelligent_chunking(request.text, self.translator_tokenizer, 400)
        _log(f"  {len(chunks)} chunks created")

        _log(f"Step 2: Translating {len(chunks)} chunks ({request.source_lang} -> {request.target_lang})")
        translated = []

        for i, chunk in enumerate(chunks, 1):
            inputs = self.translator_tokenizer(chunk, return_tensors="pt").to(self.device)
            with torch.inference_mode():
                outputs = self.translator_model.generate(**inputs, max_new_tokens=512)
            decoded = self.translator_tokenizer.decode(outputs[0], skip_special_tokens=True)
            translated.append(decoded)

            if i % 5 == 0 or i == len(chunks):
                _log(f"  Translated {i}/{len(chunks)} chunks")

        result = "\n\n".join(translated)
        _log(f"  Translation complete in {time.time() - t_start:.1f}s ({len(result):,} chars)")
        return result

    def summarize_chunk(self, text: str, context: str = "") -> str:
        chunk_text = text.strip()
        if context:
            chunk_text = f"Context: {context}\n\n{chunk_text}"
        return summarize_text(chunk_text)

    # ── SUMMARIZE ─────────────────────────────────────────────────────────────
    def summarize(self, request: SummarizeRequest) -> dict:
        t_start = time.time()

        text = request.text or ""

        # Cleaning
        _log(f"Step 1: Cleaning text ({len(text):,} chars)")
        text = remove_header_metadata(text)
        text = remove_keywords(text)
        text = remove_references(text)
        text = remove_section_headings(text)
        text = clean_text(text)

        if not text:
            text = clean_research_text(request.text)

        _log(f"  Clean text: {len(text):,} chars")

        # Section detection
        _log("Step 2: Detecting sections")
        sections = split_into_sections(text)
        non_empty = [k for k, v in sections.items() if v.strip()]
        _log(f"  Found {len(non_empty)} sections: {', '.join(non_empty)}")

        # Count total chunks
        total_chunks = 0
        for name, content in sections.items():
            if not content.strip():
                continue
            if len(content) > MAX_CHUNK_CHARS:
                total_chunks += min(3, (len(content) + MAX_CHUNK_CHARS - 1) // MAX_CHUNK_CHARS)
            else:
                total_chunks += 1

        _log(f"Step 3: Summarizing {total_chunks} chunks ({SUMMARIZATION_MODEL})")

        section_summaries = {}
        chunk_counter = 0

        for name, content in sections.items():
            if not content.strip():
                continue

            if len(content) > MAX_CHUNK_CHARS:
                sub_chunks = [content[i:i + MAX_CHUNK_CHARS] for i in range(0, len(content), MAX_CHUNK_CHARS)]
                chunk_summaries = []
                for chunk in sub_chunks[:3]:
                    chunk_counter += 1
                    _log(f"  Summarizing chunk {chunk_counter}/{total_chunks} ({name})")
                    chunk_summaries.append(self.summarize_chunk(chunk))
                combined = " ".join(chunk_summaries)
            else:
                chunk_counter += 1
                combined = content

            section_summaries[name] = self.summarize_chunk(combined)

        _log(f"Step 4: Generating final summary")
        combined_text = " ".join(section_summaries.values())
        final_summary = self.summarize_chunk(
            combined_text,
            context="This is a combination of section summaries. Produce a single cohesive final summary."
        )

        _log(f"  Summarization complete in {time.time() - t_start:.1f}s | "
             f"{len(non_empty)} sections | {len(final_summary.split())} words")

        return {
            "sections": section_summaries,
            "final_summary": final_summary
        }


# Singleton
model_service = ModelService()