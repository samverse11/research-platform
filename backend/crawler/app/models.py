# app/models.py
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class PaperSource(str, Enum):
    """Available paper sources"""
    OPENALEX = "openalex"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    ARXIV = "arxiv"
    IEEE = "ieee"
    SPRINGER = "springer"
    OPENREVIEW = "openreview"
    CROSSREF = "crossref"
    DBLP = "dblp"
    PUBMED = "pubmed"
    ACL = "acl"
    GOOGLE_SCHOLAR = "google_scholar"

class Paper(BaseModel):
    """Research paper with complete metadata"""
    title: str
    abstract: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    venue: Optional[str] = None
    year: Optional[int] = None
    authors: Optional[List[str]] = None
    source: str
    citation_count: Optional[int] = None
    pdf_url: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Attention Is All You Need",
                "abstract": "The dominant sequence transduction models.. .",
                "url": "https://arxiv.org/abs/1706.03762",
                "doi": "10.48550/arXiv.1706.03762",
                "venue":  "NeurIPS",
                "year": 2017,
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
                "source": "arxiv",
                "citation_count": 50000,
                "pdf_url":  "https://arxiv.org/pdf/1706.03762.pdf"
            }
        }

class RankedPaper(Paper):
    """Paper with similarity score"""
    similarity_score: float = Field(... , ge=0.0, le=1.0)
    rank: Optional[int] = None

class SearchRequest(BaseModel):
    """Search query request"""
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=100)
    sources: List[str] = Field(
        default=["openalex", "semantic_scholar", "arxiv"],
        description="Sources to search from"
    )
    min_year: Optional[int] = Field(default=2015, ge=1900, le=2030)
    max_year: Optional[int] = Field(default=2024, ge=1900, le=2030)
    use_cache: bool = Field(default=True)
    
    class Config: 
        json_schema_extra = {
            "example": {
                "query": "transformer neural networks attention mechanism",
                "top_k": 10,
                "sources": ["openalex", "semantic_scholar", "arxiv", "ieee"],
                "min_year":  2017,
                "max_year":  2024
            }
        }

class SearchResponse(BaseModel):
    """Search results response"""
    query: str
    total_fetched: int
    total_returned: int
    papers: List[RankedPaper]
    processing_time_seconds: float
    sources_used: List[str]
    cache_hit: bool = False

class HealthResponse(BaseModel):
    """Health check response"""
    status:  str
    timestamp: datetime
    version: str
    embedding_model: str
    device: str
    vector_db_enabled: bool
    available_sources: List[str]

class SourceInfo(BaseModel):
    """Information about a paper source"""
    id: str
    name: str
    requires_api_key: bool
    status: str
    description: Optional[str] = None
    message: Optional[str] = None
    coverage: Optional[str] = None