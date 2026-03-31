# backend/analyzer/app/main.py  —  v3.0  pymupdf + LazyGraphRAG + Vision
#
# v3.0 changes:
#   - PyMuPDF (fitz) as primary PDF parser — milliseconds vs 2+ min docling
#   - pypdf as fallback only
#   - Citation graph builder (LazyGraphRAG-inspired)
#   - Groq Vision for image-rendered formula extraction
#   - 3 Groq calls per paper (parallel inside each paper)
#   - Parallel paper processing (max_workers=5)
#   - New output: claim_verification, research_gaps, contradiction_hints
#   - Cross-paper gap analysis

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json, asyncio, tempfile, traceback, warnings, time, re, uuid, base64
from pathlib import Path
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

warnings.filterwarnings("ignore")

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import groq as groq_sdk

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

try:
    from tqdm import tqdm
    from functools import partialmethod
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)
except ImportError:
    pass

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

app = FastAPI(title="Analyzer Module", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Parallel paper processing — up to 5 papers at once
executor = ThreadPoolExecutor(max_workers=5)

JOBS: Dict[str, dict] = {}

# ── Job helpers ───────────────────────────────────────────────────────────────
class JobStatus(str, Enum):
    QUEUED="queued"; EXTRACTING="extracting"; ANALYZING="analyzing"
    COMPLETE="complete"; FAILED="failed"

def new_job(filenames):
    jid = str(uuid.uuid4())[:8]
    JOBS[jid] = {
        "status": JobStatus.QUEUED, "progress": 0, "message": "Queued…",
        "papers": {fn: {"status":"queued","message":""} for fn in filenames},
        "result": None, "error": None, "created": time.time(),
    }
    return jid

def upd(jid, **kw):
    if jid in JOBS: JOBS[jid].update(kw)

def upd_paper(jid, fn, **kw):
    if jid in JOBS: JOBS[jid]["papers"][fn].update(kw)

def safe(v, default=""):
    if v is None: return default
    if isinstance(v, (list, dict)): return str(v)
    try: return str(v)
    except: return default

# ── Pydantic models ───────────────────────────────────────────────────────────
class FormulaEntry(BaseModel):
    name: str
    latex: Optional[str] = ""
    meaning: Optional[str] = ""
    explanation: Optional[str] = ""
    purpose: Optional[str] = ""
    results_obtained: Optional[str] = "N/A"
    page: Optional[int] = None
    section: Optional[str] = ""
    source: Optional[str] = "text"   # "text" or "image"

class MetricEntry(BaseModel):
    name: str
    value: str
    context: str
    page: Optional[int] = None

class MethodologyStep(BaseModel):
    step_number: int
    title: str
    description: str
    key_detail: Optional[str] = ""

class PotentialIssue(BaseModel):
    severity: str
    title: str
    detail: str

class ComparisonData(BaseModel):
    factors: Dict[str, str]

class ClaimEntry(BaseModel):
    claim: str
    section: str
    page: Optional[int] = None
    citations_found: List[str] = []
    status: str  # "supported" | "unsupported" | "original_contribution"
    risk_note: Optional[str] = ""

class ResearchGap(BaseModel):
    gap_type: str
    description: str
    significance: str

class ContradictionHint(BaseModel):
    description: str
    section_a: str
    section_b: str

class PaperResult(BaseModel):
    filename: str
    paper_title: str
    pages: int
    formulas: List[FormulaEntry]
    metrics: List[MetricEntry]
    methodology_steps: List[MethodologyStep]
    potential_issues: List[PotentialIssue]
    comparison: ComparisonData
    # New v3.0 fields
    claim_verification: List[ClaimEntry] = []
    research_gaps: List[ResearchGap] = []
    contradiction_hints: List[ContradictionHint] = []
    citation_graph_size: int = 0
    image_formulas_found: int = 0

class MetricAlignmentRow(BaseModel):
    metric_name: str
    values: Dict[str, str]
    has_gap: bool

class FormulaRegistryEntry(BaseModel):
    canonical_name: str
    occurrences: List[Dict[str, Any]]
    shared_symbols: List[str]

class ComparisonRow(BaseModel):
    factor: str
    values: Dict[str, str]

class AnalysisResult(BaseModel):
    papers: List[PaperResult]
    comparison_table: List[ComparisonRow]
    metric_alignment: List[MetricAlignmentRow]
    formula_registry: List[FormulaRegistryEntry]
    total_seconds: int
    cross_paper_gaps: List[dict] = []

class SubmitResponse(BaseModel):
    job_id: str; message: str

class StatusResponse(BaseModel):
    job_id: str; status: str; progress: int; message: str
    papers: dict; result: Optional[dict]=None; error: Optional[str]=None

# ── PDF Extraction — PyMuPDF primary, pypdf fallback ─────────────────────────
def _extract_pypdf(path: str) -> dict:
    """Fallback PDF extractor using pypdf."""
    try:
        import pypdf
        parts = []
        with open(path, "rb") as f:
            r = pypdf.PdfReader(f)
            pages = len(r.pages)
            for p in r.pages:
                parts.append(p.extract_text() or "")
        return {
            "text": "\n".join(parts),
            "pages": pages,
            "sections": [{"heading": "Document", "text": "\n".join(parts),
                          "page_num": 1, "citations": [], "has_images": False}],
            "images": []
        }
    except Exception as e:
        print(f"  ⚠️ pypdf fallback failed: {e}")
        return {"text": "", "pages": 0, "sections": [], "images": []}


def _extract_pymupdf(path: str) -> dict:
    """
    Fast PDF extraction using PyMuPDF (fitz).
    Returns text, pages, structured sections, and image crops for formula detection.
    Falls back to pypdf if fitz is not available.
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        print("  ⚠️ PyMuPDF not installed — falling back to pypdf. Run: pip install pymupdf")
        return _extract_pypdf(path)

    try:
        doc = fitz.open(path)
        pages_count = len(doc)
        full_text_pages = []
        sections = []
        images = []

        current_section = {
            "heading": "Introduction",
            "text": "",
            "page_num": 1,
            "citations": [],
            "has_images": False
        }

        for page_num, page in enumerate(doc, start=1):
            blocks = page.get_text("dict")["blocks"]
            page_text = ""

            for block in blocks:
                if block["type"] == 0:  # text block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            font_size = span["size"]
                            if not text:
                                continue
                            # Detect headings: font>13pt, ALL CAPS, bold, or numbered section
                            is_bold = bool(span.get("flags", 0) & 16)
                            is_numbered = bool(re.match(
                                r"^\d+\.?\d*\s+[A-Z][a-zA-Z ]{3,40}$", text.strip()))
                            is_heading = (
                                font_size > 13 or
                                (text.isupper() and 2 < len(text.split()) <= 7) or
                                (is_bold and 3 < len(text.split()) <= 10) or
                                is_numbered
                            )
                            if is_heading and len(text) > 3:
                                # Save previous section
                                if current_section["text"].strip():
                                    sections.append(current_section.copy())
                                current_section = {
                                    "heading": text,
                                    "text": "",
                                    "page_num": page_num,
                                    "citations": [],
                                    "has_images": False
                                }
                            else:
                                page_text += text + " "
                                current_section["text"] += text + " "

                elif block["type"] == 1:  # image block
                    try:
                        bbox = block["bbox"]
                        clip = fitz.Rect(bbox)
                        mat = fitz.Matrix(2, 2)  # 2x zoom for clarity
                        pix = page.get_pixmap(matrix=mat, clip=clip)
                        img_bytes = pix.tobytes("png")
                        images.append({
                            "page_num": page_num,
                            "image_bytes": img_bytes,
                            "bbox": bbox,
                            "section": current_section["heading"]
                        })
                        current_section["has_images"] = True
                    except Exception:
                        pass

            full_text_pages.append(page_text)

        # Save last section
        if current_section["text"].strip():
            sections.append(current_section)

        # Extract citations from each section
        citation_patterns = [
            r'\[([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}[a-z]?)\]',
            r'\[(\d+)\]',
            r'\(([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4})\)',
        ]
        for section in sections:
            found = []
            for pattern in citation_patterns:
                found.extend(re.findall(pattern, section["text"]))
            section["citations"] = list(set(found))

        doc.close()

        return {
            "text": "\n".join(full_text_pages),
            "pages": pages_count,
            "sections": sections,
            "images": images
        }

    except Exception as e:
        print(f"  ⚠️ PyMuPDF extraction failed: {e} — falling back to pypdf")
        return _extract_pypdf(path)


# ── Citation Graph Builder (LazyGraphRAG-inspired) ────────────────────────────
def _build_citation_graph(sections: list) -> list:
    """
    Build a lazy citation graph from extracted sections.
    Each node = one text chunk with section context, page, citations, and neighbours.
    No LLM needed — built purely from extracted structure.
    """
    graph = []
    for i, section in enumerate(sections):
        node = {
            "id": f"chunk_{i:03d}",
            "heading": section["heading"],
            "text": section["text"][:1500],
            "page_num": section["page_num"],
            "citations": section["citations"],
            "has_images": section["has_images"],
            "prev_section": sections[i-1]["heading"] if i > 0 else None,
            "next_section": sections[i+1]["heading"] if i < len(sections)-1 else None,
        }
        graph.append(node)
    return graph


def _build_graph_summary(graph: list) -> str:
    """
    Compact text representation of citation graph for Groq.
    Hard capped at 3000 chars to stay within token limits.
    """
    lines = []
    for node in graph:
        cites = ", ".join(node["citations"][:5]) if node["citations"] else "none"
        lines.append(
            f'[{node["id"]}] Section: "{node["heading"]}" | Page: {node["page_num"]} | '
            f'Citations: {cites} | '
            f'Text: {node["text"][:200].strip()}...'
        )
    return "\n".join(lines)[:3000]


# ── Groq Vision — Formula Image Extraction ────────────────────────────────────
def _extract_formula_from_image(img_bytes: bytes, page_num: int, section: str) -> Optional[dict]:
    """
    Send an image crop to Groq Vision to extract formula as LaTeX.
    Uses meta-llama/llama-4-scout-17b-16e-instruct (vision-capable).
    Returns formula dict or None if no formula detected.
    """
    client = groq_sdk.Groq(api_key=GROQ_API_KEY)
    try:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": (
                            "Look at this image from a research paper. "
                            "If it contains a mathematical formula or equation, "
                            "extract it as LaTeX and return ONLY this JSON:\n"
                            '{"has_formula": true, "latex": "...", "meaning": "brief description"}\n'
                            "If it does NOT contain a formula (e.g. it is a figure, chart, "
                            "logo, diagram, or photo), "
                            'return ONLY: {"has_formula": false}'
                        )
                    }
                ]
            }],
            max_tokens=300,
            temperature=0.05
        )
        raw = resp.choices[0].message.content or ""
        data = _parse_groq_response(raw)
        if data.get("has_formula") and data.get("latex"):
            return {
                "name": f"Formula (image) — {section}",
                "latex": data["latex"],
                "meaning": data.get("meaning", ""),
                "explanation": "Extracted from image via Groq Vision (LaTeX-OCR)",
                "purpose": "Found as image in paper — text extraction not possible for this formula",
                "results_obtained": "N/A",
                "page": page_num,
                "section": section,
                "source": "image"
            }
    except Exception as e:
        print(f"  ⚠️ Vision extraction failed page {page_num}: {e}")
    return None


# ── Section splitter (unchanged from v2) ─────────────────────────────────────
def _sections(text: str):
    """
    front  = first 3000 chars  — title, abstract, intro
    body   = 8000 chars from 12%-62% — problem formulation, methods, formulas, experiments
    tail   = last 2000 chars   — conclusion, references

    12%-62% of a 60k paper = chars 7k-37k = covers pages 2-9 of a 15-page paper.
    This captures early formulas (page 3-4) AND contrastive loss / experiments (page 5-7).
    """
    n = len(text)
    front      = text[:3000]
    body_start = max(3000, int(n * 0.12))
    body_end   = min(n,    int(n * 0.62))
    body       = text[body_start:body_end][:8000]
    tail       = text[-2000:] if n > 5000 else ""
    return front, body, tail


# ── Groq Prompts (call1, call2 unchanged; call3 new) ─────────────────────────
def _prompt_call1(filename: str, pages: int, front: str, tail: str, middle: str = "") -> str:
    """Metadata + comparison — uses front + middle + tail for richer coverage."""
    return (
        'You are analyzing a research paper. Extract ONLY what is explicitly written.\n'
        'Return ONLY valid JSON, no markdown, no explanation.\n\n'
        'STRICT RULES:\n'
        '- If a field is not found in the text, use empty string "". Never guess or invent.\n'
        '- Authors: look for author byline near the title. If not visible, use "".\n'
        '- Year: look for publication date near title or in footer. If not visible, use "".\n'
        '- Citations: count reference entries at the end if visible, else use "".\n\n'
        'JSON schema:\n'
        '{\n'
        '  "paper_title": "full title exactly as written",\n'
        '  "comparison": {\n'
        '    "Authors": "all author names as listed, or empty string if not visible",\n'
        '    "Year": "4-digit year or empty string",\n'
        '    "Citations": "integer count of references or empty string",\n'
        '    "Dataset & Benchmarks": "all datasets named with sizes/splits",\n'
        '    "Model Architecture": "architecture type, layers, heads, parameters",\n'
        '    "Core Methods": "the key algorithm or technical contribution",\n'
        '    "Training Setup": "optimizer, learning rate, batch size, hardware",\n'
        '    "Baseline Models": "all models this paper compares against",\n'
        '    "Key Results": "best numbers reported with dataset context",\n'
        '    "Advantages": "stated strengths of the proposed approach",\n'
        '    "Uniqueness": "what is novel — stated by the authors",\n'
        '    "Limitations": "limitations explicitly stated by authors",\n'
        '    "Future Work": "future directions explicitly mentioned"\n'
        '  }\n'
        '}\n\n'
        'STRICT: Fill as many comparison fields as possible from all text provided.\n\n'
        'File: ' + filename + ' | Pages: ' + str(pages) + '\n\n'
        'PAPER START:\n' + front + '\n\n'
        + ('PAPER MIDDLE (methods/results):\n' + middle + '\n\n' if middle else '')
        + 'PAPER END (references/conclusion):\n' + tail
    )


def _formula_scan_prompt(body: str) -> str:
    """Dedicated formula extraction — scans one chunk of body text."""
    return (
        'You are a math formula extractor for research papers.\n'
        'Return ONLY valid JSON. No markdown, no explanation.\n\n'
        'YOUR ONLY JOB: Find every mathematical formula, equation, or expression in the text.\n\n'
        'CRITICAL RULES:\n'
        '- ONLY extract formulas you can literally read in the text below.\n'
        '- A formula is any expression with math symbols: =, +, -, *, /, sum, log, exp,\n'
        '  Greek letters (alpha, beta, theta...), subscripts, fractions, etc.\n'
        '- Do NOT invent or guess formulas. If text says "we use cross-entropy loss"\n'
        '  WITHOUT showing the equation, do NOT include it.\n'
        '- Convert what you see into proper LaTeX notation.\n'
        '- If NO formulas are visible in the text, return {"formulas": []}.\n\n'
        '{"formulas": [\n'
        '  {\n'
        '    "name": "descriptive name for this formula",\n'
        '    "latex": "proper LaTeX e.g. L = -\\\\sum_{i=1}^{N} y_i \\\\log(\\\\hat{y}_i)",\n'
        '    "meaning": "what this formula computes in one sentence",\n'
        '    "explanation": "define each symbol: y_i = true label, N = batch size, etc.",\n'
        '    "purpose": "why the paper uses this specific formula",\n'
        '    "results_obtained": "numerical value this produced e.g. loss=0.23, or N/A",\n'
        '    "page": 0,\n'
        '    "section": "section name where this appears"\n'
        '  }\n'
        ']}\n\n'
        'TEXT TO SCAN:\n' + body
    )


def _method_metrics_prompt(body: str) -> str:
    """Methodology + metrics + issues extraction."""
    return (
        'You are analyzing a research paper methods section.\n'
        'Return ONLY valid JSON. No markdown, no explanation.\n\n'
        'RULES:\n'
        '- methodology_steps: Extract 5-8 concrete steps the paper describes.\n'
        '  Each step must include: what was done, how it was done, and why.\n'
        '  key_detail must be a SPECIFIC value from paper (e.g. "BERT-base, 12 layers,\n'
        '  768 hidden, trained on SQuAD 1.1 for 3 epochs with lr=2e-5").\n'
        '- metrics: only numbers explicitly stated in the text.\n'
        '- potential_issues: 2-4 genuine concerns an expert reviewer would raise.\n'
        '  Think: is the dataset small? No ablation? Unfair baseline comparison?\n'
        '  Reproducibility concerns? Computational cost not reported?\n\n'
        '{\n'
        '  "methodology_steps": [\n'
        '    {\n'
        '      "step_number": 1,\n'
        '      "title": "precise step name",\n'
        '      "description": "3-4 sentences: what was done, how, and why. Quote specific details.",\n'
        '      "key_detail": "exact model/dataset/hyperparameter/formula from paper"\n'
        '    }\n'
        '  ],\n'
        '  "metrics": [\n'
        '    {\n'
        '      "name": "metric name e.g. F1, BLEU-4, Perplexity",\n'
        '      "value": "exact number from text e.g. 91.2%",\n'
        '      "context": "dataset and experimental condition",\n'
        '      "page": 0\n'
        '    }\n'
        '  ],\n'
        '  "potential_issues": [\n'
        '    {\n'
        '      "severity": "strong or issue or critical",\n'
        '      "title": "issue title",\n'
        '      "detail": "specific evidence from the paper"\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        'PAPER TEXT:\n' + body
    )

def _prompt_formulas(body: str) -> str:
    """Call A — formula extraction. Handles garbled PDF math text."""
    return (
        'You are a mathematical formula extractor for academic papers.\n'
        'Return ONLY valid JSON. No markdown, no explanation.\n\n'
        'IMPORTANT: PDF text extraction often garbles math. You will see things like:\n'
        '  "H T (G) = P α∈T H T (G; α)" or "arg min T :height(T )≤L H T S2 (G)"\n'
        'These ARE formulas — just rendered as broken text by the PDF parser.\n'
        'Your job is to RECONSTRUCT them into clean LaTeX.\n\n'
        'RULES:\n'
        '- Extract ALL equations, whether cleanly typeset or garbled.\n'
        '- Look for patterns: variable = expression, argmin/argmax, sum/product notation,\n'
        '  Greek letters (α β γ λ τ θ), subscripts written as _v or as separate chars.\n'
        '- Convert each to proper LaTeX (e.g. H_T(G;\\alpha) = -\\frac{g_\\alpha}{Vol(G)}...).\n'
        '- Give each formula a clear name based on what it computes.\n'
        '- For explanation: define EVERY symbol used.\n'
        '- For purpose: explain specifically WHY this paper needs this formula.\n\n'
        '{\n'
        '  "formulas": [\n'
        '    {\n'
        '      "name": "descriptive name e.g. Semantic-Structural Entropy",\n'
        '      "latex": "clean LaTeX e.g. H_{S^2}(G;\\alpha) = H_T(G;\\alpha) + \\lambda H_{sem}(V_\\alpha)",\n'
        '      "meaning": "one sentence: what quantity this formula computes",\n'
        '      "explanation": "define every symbol: alpha=tree node, lambda=balance weight, etc.",\n'
        '      "purpose": "specifically why the authors introduce this formula in their system",\n'
        '      "results_obtained": "numerical value if reported, else N/A",\n'
        '      "page": 0,\n'
        '      "section": "section name"\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        'PAPER TEXT:\n' + body
    )


def _prompt_methods_issues(body: str) -> str:
    """Call B — methodology + metrics + issues."""
    return (
        'You are a senior researcher analyzing a paper\'s methodology.\n'
        'Return ONLY valid JSON. No markdown, no explanation.\n\n'
        'RULES FOR methodology_steps:\n'
        '- Extract 5-8 steps. Use research language, not casual language.\n'
        '- Each description MUST answer three questions:\n'
        '  WHAT: what technical component or process is described\n'
        '  HOW: the specific technique, model, or algorithm used\n'
        '  WHY: the motivation — what problem does this step solve\n'
        '- key_detail: ONE specific value from paper (model name, metric, dataset, hyperparameter).\n\n'
        'RULES FOR potential_issues (write like a peer reviewer):\n'
        '- 4-6 issues. Each must cite SPECIFIC evidence from the text.\n'
        '- Consider: generalization beyond tested domains, scalability claims without proof,\n'
        '  missing ablations, offline preprocessing cost not discussed for deployment,\n'
        '  limited baseline diversity, evaluation only on accuracy (missing latency/cost),\n'
        '  no error analysis, hyperparameter sensitivity not fully explored.\n'
        '- severity "critical" = fundamental flaw; "issue" = notable weakness; "strong" = strength.\n\n'
        '{\n'
        '  "methodology_steps": [\n'
        '    {\n'
        '      "step_number": 1,\n'
        '      "title": "precise technical step name",\n'
        '      "description": "WHAT: [component]. HOW: [technique used]. WHY: [motivation from paper].",\n'
        '      "key_detail": "specific value e.g. Sentence-BERT encoder, k=6 retrieved subgraphs"\n'
        '    }\n'
        '  ],\n'
        '  "metrics": [\n'
        '    {"name": "metric name", "value": "exact number", "context": "dataset+condition", "page": 0}\n'
        '  ],\n'
        '  "potential_issues": [\n'
        '    {\n'
        '      "severity": "strong or issue or critical",\n'
        '      "title": "issue title",\n'
        '      "detail": "specific evidence: quote or reference exact claim from paper"\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        'PAPER TEXT:\n' + body
    )



def _prompt_call3(filename: str, graph_summary: str) -> str:
    """
    Call 3: Claim verification + research gaps + contradictions.
    Receives the citation graph summary — grounded structured context.
    """
    return (
        'You are a research paper reviewer analyzing claims and research gaps.\n'
        'You have been given a structured citation graph — each chunk has its section, page, and citations.\n'
        'Return ONLY valid JSON, no markdown, no explanation.\n\n'
        'STRICT RULES:\n'
        '- claim_verification: identify 3-6 major claims the paper makes.\n'
        '  For each claim, check if it has a citation in the same chunk.\n'
        '  If cited: status = "supported".\n'
        '  If no citation but it is the paper\'s own result: status = "original_contribution".\n'
        '  If no citation and not clearly the paper\'s own result: status = "unsupported".\n'
        '- research_gaps: what has this paper NOT tested? Consider:\n'
        '  languages not tested, datasets not used, model sizes not compared,\n'
        '  domains not covered (medical, legal, etc.), evaluation metrics missing.\n'
        '- contradiction_hints: any internal inconsistency in the claims across sections.\n\n'
        'JSON schema:\n'
        '{\n'
        '  "claim_verification": [\n'
        '    {\n'
        '      "claim": "exact claim from paper",\n'
        '      "section": "which section this appears in",\n'
        '      "page": 0,\n'
        '      "citations_found": ["list of citations in same chunk"],\n'
        '      "status": "supported | unsupported | original_contribution",\n'
        '      "risk_note": "why this might be a concern if unsupported"\n'
        '    }\n'
        '  ],\n'
        '  "research_gaps": [\n'
        '    {\n'
        '      "gap_type": "language | dataset | model | domain | metric | other",\n'
        '      "description": "what was not tested or evaluated",\n'
        '      "significance": "why this gap matters"\n'
        '    }\n'
        '  ],\n'
        '  "contradiction_hints": [\n'
        '    {\n'
        '      "description": "what seems inconsistent",\n'
        '      "section_a": "first mention location",\n'
        '      "section_b": "conflicting mention location"\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        'File: ' + filename + '\n\n'
        'CITATION GRAPH SUMMARY:\n' + graph_summary
    )


# ── JSON parser (unchanged) ───────────────────────────────────────────────────
def _parse_groq_response(raw: str) -> dict:
    """Robustly parse JSON from Groq response."""
    raw = raw.strip()
    if "```" in raw:
        for part in raw.split("```"):
            p = part.strip().lstrip("json").strip()
            if p.startswith("{"): raw = p; break
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except: pass
    print(f"  ⚠️  JSON parse failed: {raw[:150]}")
    return {}


# ── Groq text call (unchanged) ────────────────────────────────────────────────
def _groq_call(prompt: str, max_tokens: int = 1800) -> dict:
    """Single Groq text call with rate-limit retry."""
    client = groq_sdk.Groq(api_key=GROQ_API_KEY)
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.05,
                max_tokens=max_tokens,
            )
            raw = resp.choices[0].message.content or ""
            return _parse_groq_response(raw)
        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err.lower():
                m = re.search(r'try again in (\d+(?:\.\d+)?)(ms|s)', err.lower())
                wait = ((float(m.group(1)) / 1000 if m.group(2) == "ms"
                         else float(m.group(1))) + 2.0) if m else 15 * (attempt + 1)
                print(f"  ⏳ Rate limit — waiting {wait:.0f}s (attempt {attempt+1})")
                time.sleep(wait)
            else:
                print(f"  ❌ Groq error: {err[:150]}")
                raise
    return {}


# ── Parse Groq response into PaperResult (unchanged core) ────────────────────
def parse_result(filename: str, pages: int, data: dict) -> PaperResult:
    # Formulas
    formulas = []
    seen_latex = set()
    for f in (data.get("formulas") or []):
        if not isinstance(f, dict): continue
        latex = safe(f.get("latex")).strip()
        if not latex or latex in seen_latex: continue
        seen_latex.add(latex)
        formulas.append(FormulaEntry(
            name=safe(f.get("name"), "Formula") or "Formula",
            latex=latex,
            meaning=safe(f.get("meaning")),
            explanation=safe(f.get("explanation")),
            purpose=safe(f.get("purpose")),
            results_obtained=safe(f.get("results_obtained"), "N/A"),
            page=f.get("page") if isinstance(f.get("page"), int) else None,
            section=safe(f.get("section")),
            source=safe(f.get("source"), "text"),
        ))

    # Metrics
    metrics = []
    seen_metrics = set()
    for m in (data.get("metrics") or []):
        if not isinstance(m, dict): continue
        name  = safe(m.get("name")).strip()
        value = safe(m.get("value")).strip()
        if not name or not value: continue
        key = (name.lower(), value)
        if key in seen_metrics: continue
        seen_metrics.add(key)
        metrics.append(MetricEntry(
            name=name, value=value,
            context=safe(m.get("context")),
            page=m.get("page") if isinstance(m.get("page"), int) else None,
        ))

    # Methodology steps
    steps = []
    for s in (data.get("methodology_steps") or []):
        if not isinstance(s, dict): continue
        desc = safe(s.get("description")).strip()
        if not desc: continue
        steps.append(MethodologyStep(
            step_number=int(s.get("step_number") or len(steps)+1),
            title=safe(s.get("title"), "Step") or "Step",
            description=desc,
            key_detail=safe(s.get("key_detail")) or None,
        ))
    for i, s in enumerate(steps): s.step_number = i+1

    # Potential issues
    potential_issues = []
    raw_issues = data.get("potential_issues") or data.get("issues") or []
    if not raw_issues:
        potential_issues.append(PotentialIssue(
            severity="issue", title="No issues reported",
            detail="The model did not identify specific concerns for this paper."
        ))
    for iss in raw_issues:
        if not isinstance(iss, dict): continue
        potential_issues.append(PotentialIssue(
            severity=safe(iss.get("severity"), "issue") or "issue",
            title=safe(iss.get("title"), "Issue") or "Issue",
            detail=safe(iss.get("detail")),
        ))

    # Comparison factors
    raw_comp = data.get("comparison") or {}
    factors: Dict[str, str] = {}
    if isinstance(raw_comp, dict):
        for k, v in raw_comp.items():
            val = safe(v).strip()
            if val and val.lower() not in ("", "none", "n/a", "null", "—"):
                factors[k] = val

    if metrics:
        factors["Evaluation Metrics"] = "; ".join(f"{m.name}={m.value}" for m in metrics[:20])

    title = safe(data.get("paper_title")).strip() or filename.replace(".pdf", "")

    return PaperResult(
        filename=filename,
        paper_title=title,
        pages=pages,
        formulas=formulas,
        metrics=metrics,
        methodology_steps=steps,
        potential_issues=potential_issues,
        comparison=ComparisonData(factors=factors),
    )


# ── Full paper pipeline — v3.0 ────────────────────────────────────────────────
def process_paper(jid: str, filename: str, content: bytes) -> PaperResult:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        path = tmp.name
    try:
        # STEP 1: Fast extraction with PyMuPDF
        upd_paper(jid, filename, status="extracting", message="📄 Fast parsing with PyMuPDF…")
        ext = _extract_pymupdf(path)
        pages   = ext["pages"]
        text    = ext["text"]
        sections = ext["sections"]
        images  = ext["images"]
        print(f"  [{filename}] {pages} pages | {len(text)} chars | "
              f"{len(sections)} sections | {len(images)} images")

        # STEP 2: Build citation graph (no LLM — instant)
        upd_paper(jid, filename, status="analyzing", message="🔗 Building citation graph…")
        citation_graph  = _build_citation_graph(sections)
        graph_summary   = _build_graph_summary(citation_graph)
        print(f"  [{filename}] Citation graph: {len(citation_graph)} nodes")

        # STEP 3: Formula image extraction via Groq Vision
        # Filter: skip tiny icons/logos, skip massive full-page figures
        # Formula images are typically 2k-200k bytes — narrow width, short height
        image_formulas = []
        if images:
            formula_images = [
                img for img in images
                if 2000 < len(img["image_bytes"]) < 200_000
            ][:6]  # max 6 per paper — each vision call costs ~3s

            if formula_images:
                upd_paper(jid, filename, status="analyzing",
                          message=f"🔬 Scanning {len(formula_images)} images for formulas…")
                for img in formula_images:
                    result = _extract_formula_from_image(
                        img["image_bytes"], img["page_num"], img["section"]
                    )
                    if result:
                        image_formulas.append(result)
                print(f"  [{filename}] {len(image_formulas)} image formulas found")

        # STEP 4: THREE parallel Groq calls + ONE sequential call using citation graph
        # Calls 1, A, B run in parallel:
        #   Call 1: front+tail       → title, comparison metadata
        #   Call A: body             → formulas ONLY (focused, no token overflow)
        #   Call B: body             → methodology + metrics + issues
        # Call C: graph_summary      → claim verification + research gaps
        #   (runs after A+B so graph is ready; uses citation graph as grounded context)
        front, body, tail = _sections(text)
        upd_paper(jid, filename, status="analyzing",
                  message="🤖 Analyzing paper (parallel calls)…")

        with ThreadPoolExecutor(max_workers=3) as paper_executor:
            middle   = text[int(len(text)*0.42):int(len(text)*0.42)+1500]
            future1  = paper_executor.submit(
                _groq_call, _prompt_call1(filename, pages, front, tail, middle), 1800)
            futureA  = paper_executor.submit(
                _groq_call, _prompt_formulas(body), 2000)
            futureB  = paper_executor.submit(
                _groq_call, _prompt_methods_issues(body), 2500)
            d1   = future1.result()
            dA   = futureA.result()
            dB   = futureB.result()

        print(f"  [{filename}] Parallel done — "
              f"{len(dA.get('formulas') or [])} formulas, "
              f"{len(dB.get('methodology_steps') or [])} steps, "
              f"{len(dB.get('potential_issues') or [])} issues")

        # Call C skipped — citation graph summary alone is insufficient context
        # for reliable claim verification. Keeping empty rather than showing wrong data.
        dC = {}

        # Deduplicate text formulas
        seen_f = set()
        all_text_formulas = []
        for f in (dA.get("formulas") or []):
            key = (f.get("name", "") + f.get("latex", "")).strip().lower()[:60]
            if key and key not in seen_f:
                seen_f.add(key)
                all_text_formulas.append(f)

        # Merge text + image formulas
        all_formulas = all_text_formulas + image_formulas

        # STEP 5: Parse claims + gaps from citation-graph-grounded Call C
        raw_claims = dC.get("claim_verification") or []
        claims = []
        for c in raw_claims:
            if not isinstance(c, dict): continue
            claims.append(ClaimEntry(
                claim=safe(c.get("claim")),
                section=safe(c.get("section")),
                page=c.get("page") if isinstance(c.get("page"), int) else None,
                citations_found=c.get("citations_found") or [],
                status=safe(c.get("status"), "unsupported"),
                risk_note=safe(c.get("risk_note")),
            ))

        raw_gaps = dC.get("research_gaps") or []
        gaps = []
        for g in raw_gaps:
            if not isinstance(g, dict): continue
            gaps.append(ResearchGap(
                gap_type=safe(g.get("gap_type"), "other"),
                description=safe(g.get("description")),
                significance=safe(g.get("significance")),
            ))

        raw_contradictions = dC.get("contradiction_hints") or []
        contradictions = []
        for ct in raw_contradictions:
            if not isinstance(ct, dict): continue
            contradictions.append(ContradictionHint(
                description=safe(ct.get("description")),
                section_a=safe(ct.get("section_a")),
                section_b=safe(ct.get("section_b")),
            ))

        # STEP 6: Merge all results
        merged = {
            "paper_title":       d1.get("paper_title") or filename.replace(".pdf", ""),
            "comparison":        d1.get("comparison") or {},
            "formulas":          all_formulas,
            "metrics":           dB.get("metrics") or [],
            "methodology_steps": dB.get("methodology_steps") or [],
            "potential_issues":  dB.get("potential_issues") or [],
        }

        if not merged["paper_title"] and not all_formulas and not merged["metrics"]:
            raise ValueError("All Groq calls returned empty — check API key or paper content")

        result = parse_result(filename, pages, merged)

        # Attach new v3.0 fields
        result.claim_verification  = claims
        result.research_gaps       = gaps
        result.contradiction_hints = contradictions
        result.citation_graph_size = len(citation_graph)
        result.image_formulas_found = len(image_formulas)

        upd_paper(jid, filename, status="complete",
                  message=(
                      f"✅ {len(result.formulas)} formulas "
                      f"({result.image_formulas_found} from images) · "
                      f"{len(result.metrics)} metrics · "
                      f"{len(result.methodology_steps)} steps · "
                      f"{len(result.claim_verification)} claims · "
                      f"{len(result.research_gaps)} gaps"
                  ))
        print(f"  [{filename}] ✅ DONE")
        return result

    finally:
        os.unlink(path)


# ── Cross-paper gap analysis ──────────────────────────────────────────────────
def build_cross_paper_gaps(papers: List[PaperResult]) -> List[dict]:
    """
    Find research gaps that appear across multiple papers — highest significance.
    Only returns gaps found in 2+ papers.
    """
    if len(papers) < 2:
        return []

    gap_counts: Dict[str, dict] = {}
    for paper in papers:
        for gap in paper.research_gaps:
            key = (gap.gap_type + ": " + gap.description[:60]).lower()
            if key not in gap_counts:
                gap_counts[key] = {"gap": gap, "papers": [], "count": 0}
            gap_counts[key]["papers"].append(paper.paper_title)
            gap_counts[key]["count"] += 1

    shared = []
    for _, data in gap_counts.items():
        if data["count"] >= 2:
            shared.append({
                "gap_type":        data["gap"].gap_type,
                "description":     data["gap"].description,
                "significance":    data["gap"].significance,
                "found_in_papers": data["papers"],
                "importance":      "HIGH — multiple papers share this gap"
            })

    return sorted(shared, key=lambda x: len(x["found_in_papers"]), reverse=True)


# ── Cross-paper builders (unchanged) ─────────────────────────────────────────
def build_comparison_table(papers: List[PaperResult]) -> List[ComparisonRow]:
    all_factors: set = set()
    for p in papers:
        for k in p.comparison.factors: all_factors.add(k)
    ORDER = [
        "Authors", "Year", "Citations",
        "Dataset & Benchmarks", "Model Architecture", "Core Methods",
        "Training Setup", "Baseline Models", "Key Results", "Evaluation Metrics",
        "Advantages", "Uniqueness", "Limitations", "Future Work",
    ]
    ordered  = [f for f in ORDER if f in all_factors]
    ordered += sorted(f for f in all_factors if f not in ORDER)
    rows = []
    for factor in ordered:
        values = {p.paper_title: safe(p.comparison.factors.get(factor), "—") or "—"
                  for p in papers}
        rows.append(ComparisonRow(factor=factor, values=values))
    rows.append(ComparisonRow(factor="Pages",
        values={p.paper_title: str(p.pages) for p in papers}))
    return rows


def build_metric_alignment(papers: List[PaperResult]) -> List[MetricAlignmentRow]:
    metric_map: Dict[str, Dict[str, str]] = {}
    def norm(n): return n.upper().strip().replace(" ", "_").replace("-", "_")
    for paper in papers:
        for m in paper.metrics:
            key = norm(m.name)
            if key not in metric_map: metric_map[key] = {"_display": m.name}
            metric_map[key][paper.paper_title] = m.value
    rows = []
    for _, values in sorted(metric_map.items()):
        display = values.pop("_display", "?")
        rv: Dict[str, str] = {}
        has_gap = False
        for paper in papers:
            v = values.get(paper.paper_title, "—")
            rv[paper.paper_title] = v
            if v == "—": has_gap = True
        rows.append(MetricAlignmentRow(metric_name=display, values=rv, has_gap=has_gap))
    return rows


def build_formula_registry(papers: List[PaperResult]) -> List[FormulaRegistryEntry]:
    sym_re = re.compile(r'\\[a-zA-Z]+|[a-zA-Z]_\{?[a-zA-Z0-9]+\}?|[A-Z]')
    all_entries = []
    for paper in papers:
        for f in paper.formulas:
            all_entries.append({
                "paper":   paper.paper_title,
                "name":    f.name or "",
                "latex":   f.latex or "",
                "page":    f.page,
                "section": f.section,
                "source":  getattr(f, "source", "text"),
                "symbols": set(sym_re.findall(f.latex or "")),
            })
    registry: List[FormulaRegistryEntry] = []
    used: set = set()
    for i, entry in enumerate(all_entries):
        if i in used: continue
        group = [entry]; used.add(i)
        for j, other in enumerate(all_entries):
            if j in used or j == i: continue
            n1 = (entry["name"] or " ").lower().split()
            n2 = (other["name"] or " ").lower().split()
            name_match  = bool(n1) and bool(n2) and n1[0] == n2[0]
            sym_overlap = len(entry["symbols"] & other["symbols"])
            sym_thresh  = min(len(entry["symbols"]), len(other["symbols"]), 3)
            if name_match or (sym_overlap >= sym_thresh and sym_thresh > 0):
                group.append(other); used.add(j)
        if len(set(e["paper"] for e in group)) < 2: continue
        shared = set.intersection(*[e["symbols"] for e in group]) if group else set()
        occs = []
        for e in group:
            others = [o for o in group if o is not e]
            occs.append({
                "paper":        e["paper"],
                "latex":        e["latex"],
                "page":         e["page"],
                "section":      e["section"],
                "source":       e.get("source", "text"),
                "variant_note": "variant" if others and e["latex"] != others[0]["latex"] else "",
            })
        registry.append(FormulaRegistryEntry(
            canonical_name=entry["name"] or "Formula",
            occurrences=occs,
            shared_symbols=sorted(list(shared))[:10],
        ))
    return registry


# ── Async job runner ──────────────────────────────────────────────────────────
async def run_job(jid: str, file_data: List[tuple]):
    start = time.time()
    try:
        upd(jid, status=JobStatus.EXTRACTING, progress=10,
            message=f"🚀 Processing {len(file_data)} paper(s) in parallel…")

        loop  = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(executor, process_paper, jid, fn, d)
                 for fn, d in file_data]

        async def ticker():
            steps = [15, 25, 40, 55, 70, 82, 90, 95]
            for pct in steps:
                await asyncio.sleep(10)
                if JOBS.get(jid, {}).get("status") not in (JobStatus.COMPLETE, JobStatus.FAILED):
                    upd(jid, progress=pct)

        tick = asyncio.create_task(ticker())
        raw  = await asyncio.gather(*tasks, return_exceptions=True)
        tick.cancel()

        papers = []
        for i, r in enumerate(raw):
            if isinstance(r, Exception):
                traceback.print_exc()
                fn = file_data[i][0]
                upd_paper(jid, fn, status="failed", message=f"❌ {r}")
                papers.append(PaperResult(
                    filename=fn,
                    paper_title=fn.replace(".pdf", ""),
                    pages=0,
                    formulas=[], metrics=[], methodology_steps=[],
                    potential_issues=[PotentialIssue(
                        severity="critical", title="Processing Error", detail=str(r))],
                    comparison=ComparisonData(factors={}),
                ))
            else:
                papers.append(r)

        cross_gaps = build_cross_paper_gaps(papers)
        elapsed = int(time.time() - start)

        upd(jid, status=JobStatus.COMPLETE, progress=100,
            message=f"✅ Done in {elapsed}s",
            result=AnalysisResult(
                papers=papers,
                comparison_table=build_comparison_table(papers),
                metric_alignment=build_metric_alignment(papers),
                formula_registry=build_formula_registry(papers),
                total_seconds=elapsed,
                cross_paper_gaps=cross_gaps,
            ).dict())

    except Exception as e:
        traceback.print_exc()
        upd(jid, status=JobStatus.FAILED, progress=0, message=f"❌ {e}", error=str(e))


# ── Routes ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    print(f"\n{'='*60}")
    print("🔬 Analyzer v3.0  —  PyMuPDF + LazyGraphRAG + Vision")
    print(f"{'='*60}")
    print(f"   GROQ_API_KEY : {'✅' if GROQ_API_KEY else '❌ MISSING'}")
    print(f"   PDF Parser   : PyMuPDF (fitz) → pypdf fallback")
    print(f"   LLM (text)   : llama-3.1-8b-instant via Groq")
    print(f"   LLM (vision) : meta-llama/llama-4-scout-17b-16e-instruct via Groq")
    print(f"   Parallelism  : 5 papers × 3 parallel calls each")
    print(f"   New features : Citation graph · Claim verification · Research gaps")

    try:
        import fitz
        print(f"   PyMuPDF      : ✅ v{fitz.version[0]}")
    except ImportError:
        print(f"   PyMuPDF      : ❌ not installed — run: pip install pymupdf")

    print("✅ Ready\n")


@app.get("/")
async def root():
    return {"module": "analyzer", "version": "3.0.0"}


@app.get("/health")
async def health():
    pymupdf_ok = False
    try:
        import fitz
        pymupdf_ok = True
    except ImportError:
        pass
    return {
        "status":       "healthy",
        "groq_key_set": bool(GROQ_API_KEY),
        "pymupdf":      pymupdf_ok,
    }


@app.post("/analyze/submit", response_model=SubmitResponse)
async def submit(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    if not GROQ_API_KEY: raise HTTPException(500, "GROQ_API_KEY not set.")
    if not files:        raise HTTPException(422, "No files.")
    if len(files) > 3:   raise HTTPException(422, "Max 3 papers.")
    file_data = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(422, f"{f.filename} is not a PDF.")
        content = await f.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(422, f"{f.filename} > 50MB.")
        file_data.append((f.filename, content))
    jid = new_job([fn for fn, _ in file_data])
    background_tasks.add_task(run_job, jid, file_data)
    print(f"\n🚀 Job {jid} — {len(file_data)} paper(s)")
    return SubmitResponse(job_id=jid, message=f"Poll /analyze/status/{jid}")


@app.get("/analyze/status/{jid}", response_model=StatusResponse)
async def status(jid: str):
    if jid not in JOBS: raise HTTPException(404, f"Job {jid} not found.")
    j = JOBS[jid]
    return StatusResponse(
        job_id=jid, status=j["status"], progress=j["progress"],
        message=j["message"], papers=j["papers"],
        result=j.get("result"), error=j.get("error")
    )


@app.delete("/analyze/job/{jid}")
async def delete_job(jid: str):
    JOBS.pop(jid, None)
    return {"deleted": jid}