# backend/crawler/app/main.py
from fastapi import FastAPI, HTTPException
from datetime import datetime
import time
from typing import List

from . config import get_settings
from . models import (
    SearchRequest, SearchResponse, HealthResponse, SourceInfo
)
from .services.multi_source_fetcher import get_multi_source_fetcher
from . services.ranker import get_ranker
from .services.embeddings import get_embedding_service

settings = get_settings()

# Create sub-app (will be mounted by API gateway)
app = FastAPI(
    title="Crawler Module",
    version=settings.VERSION,
    description="Paper fetching and semantic search module"
)

# ❌ REMOVE CORS - Gateway handles it
# Don't add CORS middleware here

# Global services
fetcher = None
ranker = None
embedding_service = None

@app.on_event("startup")
async def startup_event():
    """Initialize services"""
    global fetcher, ranker, embedding_service
    
    print("\n" + "="*60)
    print(f"🚀 Starting Crawler Module v{settings.VERSION}")
    print("="*60 + "\n")
    
    fetcher = get_multi_source_fetcher()
    ranker = get_ranker()
    embedding_service = get_embedding_service()
    
    print("\n✅ Crawler Module initialized!\n")

@app.get("/")
async def crawler_root():
    """Crawler module root"""
    return {
        "module": "crawler",
        "version": settings.VERSION,
        "status": "operational"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check with available sources"""
    
    available = ["openalex", "semantic_scholar", "arxiv", "openreview", "crossref", "dblp", "springer"]
    
    if settings.IEEE_API_KEY:
        available.append("ieee")
    if settings.SPRINGER_API_KEY:
        available.append("springer")
    if settings.SERPAPI_KEY: 
        available.append("google_scholar")
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version=settings.VERSION,
        embedding_model=settings.EMBEDDING_MODEL,
        device=settings.DEVICE,
        vector_db_enabled=settings.USE_VECTOR_DB,
        available_sources=available
    )

# ✅ REMOVE API_PREFIX - Just use /search
@app.post("/search", response_model=SearchResponse)
async def search_papers(request: SearchRequest):
    """
    Search and rank papers from multiple sources with full metadata.
    """
    start_time = time. time()
    
    try:
        print("\n" + "="*60)
        print(f"🔎 Query:  {request.query}")
        print(f"📚 Sources:  {', '.join(request.sources)}")
        print(f"📅 Years: {request. min_year}-{request.max_year}")
        print("="*60 + "\n")
        
        # Fetch papers
        papers = fetcher.fetch_papers(
            query=request. query,
            sources=request. sources,
            max_results=settings.MAX_PAPERS_PER_SOURCE,
            min_year=request.min_year or 2015,
            max_year=request.max_year or 2024
        )
        
        if not papers:
            return SearchResponse(
                query=request.query,
                total_fetched=0,
                total_returned=0,
                papers=[],
                processing_time_seconds=time.time() - start_time,
                sources_used=request.sources
            )
        
        # Rank papers
        ranked_papers = ranker. rank_papers(
            query=request.query,
            papers=papers,
            top_k=request.top_k
        )
        
        processing_time = time.time() - start_time
        
        print(f"\n{'='*60}")
        print(f"✅ Search completed in {processing_time:.2f}s")
        print(f"📊 Returned {len(ranked_papers)} / {len(papers)} papers")
        print(f"{'='*60}\n")
        
        return SearchResponse(
            query=request.query,
            total_fetched=len(papers),
            total_returned=len(ranked_papers),
            papers=ranked_papers,
            processing_time_seconds=processing_time,
            sources_used=request.sources
        )
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ REMOVE API_PREFIX - Just use /sources
@app.get("/sources", response_model=List[SourceInfo])
async def get_available_sources():
    """Get all available sources with their status"""
    
    sources = [
        SourceInfo(
            id="openalex",
            name="OpenAlex",
            requires_api_key=False,
            status="available",
            description="250M+ papers, all fields, best coverage",
            coverage="250M+ papers"
        ),
        SourceInfo(
            id="semantic_scholar",
            name="Semantic Scholar",
            requires_api_key=False,
            status="available",
            description="AI-powered research tool with 200M+ papers",
            coverage="200M+ papers"
        ),
        SourceInfo(
            id="arxiv",
            name="ArXiv",
            requires_api_key=False,
            status="available",
            description="Preprint repository for CS, Physics, Math",
            coverage="2M+ papers"
        ),
        SourceInfo(
            id="openreview",
            name="OpenReview",
            requires_api_key=False,
            status="available",
            description="ML conferences with peer reviews",
            coverage="100K+ papers"
        ),
        SourceInfo(
            id="crossref",
            name="CrossRef",
            requires_api_key=False,
            status="available",
            description="DOI metadata for scholarly content",
            coverage="140M+ records"
        ),
        SourceInfo(
            id="dblp",
            name="DBLP",
            requires_api_key=False,
            status="available",
            description="Computer Science bibliography",
            coverage="6M+ publications"
        ),
    ]
    
    # IEEE
    if settings.IEEE_API_KEY:
        sources.append(SourceInfo(
            id="ieee",
            name="IEEE Xplore",
            requires_api_key=True,
            status="available",
            description="Engineering and CS publications",
            coverage="5M+ documents"
        ))
    else:
        sources.append(SourceInfo(
            id="ieee",
            name="IEEE Xplore",
            requires_api_key=True,
            status="unavailable",
            message="Requires IEEE_API_KEY.  Get free key at https://developer.ieee.org/",
            coverage="5M+ documents"
        ))
    
    # Springer
    if settings.SPRINGER_API_KEY:
        sources. append(SourceInfo(
            id="springer",
            name="Springer Nature",
            requires_api_key=True,
            status="available",
            description="Scientific, technical, and medical content",
            coverage="13M+ documents"
        ))
    else:
        sources.append(SourceInfo(
            id="springer",
            name="Springer Nature",
            requires_api_key=True,
            status="unavailable",
            message="Requires SPRINGER_API_KEY. Get free key at https://dev.springernature.com/",
            coverage="13M+ documents"
        ))
    
    return sources

# ✅ REMOVE API_PREFIX - Just use /stats
@app.get("/stats")
async def get_stats():
    """System statistics"""
    return {
        "module": "crawler",
        "version": settings.VERSION,
        "embedding_model": settings.EMBEDDING_MODEL,
        "device":  settings.DEVICE,
        "max_papers_per_source":  settings.MAX_PAPERS_PER_SOURCE,
        "supported_sources": 10
    }

@app.get("/debug/config")
async def debug_config():
    """Debug endpoint to check configuration"""
    return {
        "springer_key_exists": bool(settings.SPRINGER_API_KEY),
        "springer_key_length": len(settings.SPRINGER_API_KEY) if settings.SPRINGER_API_KEY else 0,
        "springer_key_preview": settings.SPRINGER_API_KEY[:10] + "..." if settings.SPRINGER_API_KEY and len(settings.SPRINGER_API_KEY) > 10 else "NOT SET",
        "ieee_key_exists": bool(settings.IEEE_API_KEY) if hasattr(settings, 'IEEE_API_KEY') else False,
        "device": settings.DEVICE,
        "embedding_model": settings. EMBEDDING_MODEL
    }