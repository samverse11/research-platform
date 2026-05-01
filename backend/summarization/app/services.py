import os
import torch
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from dotenv import load_dotenv
from groq import Groq

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

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"  # fast + smart, good for summarization
MAX_CHUNK_CHARS = 6000  # safe limit per Groq request


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

        self.groq_client = None

    def load_models(self):

        print(f"💻 Loading models on {self.device.upper()}")

        # -------------------------------
        # TRANSLATOR
        # -------------------------------
        self.translator_tokenizer = AutoTokenizer.from_pretrained(
            "Helsinki-NLP/opus-mt-de-en"
        )

        self.translator_model = AutoModelForSeq2SeqLM.from_pretrained(
            "Helsinki-NLP/opus-mt-de-en"
        ).to(self.device)

        # -------------------------------
        # GROQ CLIENT
        # -------------------------------
        if not GROQ_API_KEY:
            raise ValueError("❌ GROQ_API_KEY not found in environment variables")

        self.groq_client = Groq(api_key=GROQ_API_KEY)
        print(f"✅ Groq client initialized with model: {GROQ_MODEL}")

    # -------------------------------
    # TRANSLATE
    # -------------------------------
    def translate(self, request: TranslateRequest) -> str:

        chunks = intelligent_chunking(
            request.text,
            self.translator_tokenizer,
            400
        )

        translated = []

        for chunk in chunks:
            inputs = self.translator_tokenizer(
                chunk,
                return_tensors="pt"
            ).to(self.device)

            with torch.inference_mode():
                outputs = self.translator_model.generate(
                    **inputs,
                    max_new_tokens=512
                )

            decoded = self.translator_tokenizer.decode(
                outputs[0],
                skip_special_tokens=True
            )

            translated.append(decoded)

        return "\n\n".join(translated)

    # -------------------------------
    # GROQ SUMMARIZATION HELPER
    # -------------------------------
    def _groq_summarize_chunk(self, text: str, context: str = "") -> str:

        system_prompt = (
            "You are a scientific research summarizer. "
            "Your job is to produce clear, concise, and accurate summaries of academic and research texts. "
            "Focus on key findings, methods, and conclusions. "
            "Avoid filler phrases. Respond only with the summary, no preamble."
        )

        user_prompt = (
            f"{f'Context: {context}' if context else ''}\n\n"
            f"Summarize the following research text:\n\n{text}"
        ).strip()

        response = self.groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=512,
        )

        return response.choices[0].message.content.strip()

    # -------------------------------
    # SUMMARIZATION
    # -------------------------------
    def summarize(self, request: SummarizeRequest) -> dict:

        text = request.text or ""

        # Cleaning pipeline
        text = remove_header_metadata(text)
        text = remove_keywords(text)
        text = remove_references(text)
        text = remove_section_headings(text)
        text = clean_text(text)

        if not text:
            text = clean_research_text(request.text)

        sections = split_into_sections(text)
        section_summaries = {}

        for name, content in sections.items():

            if not content.strip():
                continue

            # If section is too long, chunk it and summarize each chunk
            if len(content) > MAX_CHUNK_CHARS:
                chunks = [
                    content[i:i + MAX_CHUNK_CHARS]
                    for i in range(0, len(content), MAX_CHUNK_CHARS)
                ]
                chunk_summaries = [
                    self._groq_summarize_chunk(chunk) for chunk in chunks[:3]
                ]
                combined = " ".join(chunk_summaries)
            else:
                combined = content

            section_summaries[name] = self._groq_summarize_chunk(combined)

        # -------------------------------
        # FINAL SUMMARY
        # -------------------------------
        combined_text = " ".join(section_summaries.values())

        final_summary = self._groq_summarize_chunk(
            combined_text,
            context="This is a combination of section summaries. Produce a single cohesive final summary."
        )

        return {
            "sections": section_summaries,
            "final_summary": final_summary
        }


# Singleton
model_service = ModelService()