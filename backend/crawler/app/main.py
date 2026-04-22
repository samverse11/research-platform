from fastapi import FastAPI, HTTPException
from datetime import datetime
import time
import traceback
from .services.vector_store import get_vector_store
from typing import List
from .services.cache_signature import (
    load_signature,
    save_signature,
    signature_for_request,
    signature_matches,
)

from .config import get_settings
from .models import (
    SearchRequest,
    SearchResponse,
    HealthResponse,
    SourceInfo,
    RankedPaper,
)
from .services.multi_source_fetcher import get_multi_source_fetcher
from .services.ranker import get_ranker
from .services.embeddings import get_embedding_service

settings = get_settings()
vector_store = None

# Create sub-app (will be mounted by API gateway)
app = FastAPI(
    title="Crawler Module",
    version=settings.VERSION,
    description="Paper fetching and semantic search module",
)

# Global services
fetcher = None
ranker = None
embedding_service = None


def dedup_ranked_papers(papers: list[RankedPaper], top_k: int) -> list[RankedPaper]:
    """
    Deduplicate for DISPLAY/RESPONSE ONLY.
    Does NOT clear or delete anything from the cache/vector store.
    Prefers DOI; falls back to title+year.
    """
    seen = set()
    unique: list[RankedPaper] = []

    for p in papers:
        if p.doi:
            doi = p.doi.strip().lower()
            doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
            key = ("doi", doi)
        else:
            title = (p.title or "").strip().lower()
            year = p.year or ""
            key = ("ty", title, year)

        if key in seen:
            continue

        seen.add(key)
        unique.append(p)

        if len(unique) >= top_k:
            break

    # re-number ranks after dedup (nice for UI)
    for i, p in enumerate(unique, start=1):
        p.rank = i

    return unique


@app.on_event("startup")
async def startup_event():
    """Initialize services"""
    global fetcher, ranker, embedding_service
    global vector_store

    print("\n" + "=" * 60)
    print(f"🚀 Starting Crawler Module v{settings.VERSION}")
    print("=" * 60 + "\n")

    fetcher = get_multi_source_fetcher()
    ranker = get_ranker()
    embedding_service = get_embedding_service()
    vector_store = get_vector_store()

    print("\n✅ Crawler Module initialized!\n")
    print("USE_VECTOR_DB =", settings.USE_VECTOR_DB)
    print("VECTOR_DB_PATH =", settings.VECTOR_DB_PATH)


@app.get("/")
async def crawler_root():
    """Crawler module root"""
    return {"module": "crawler", "version": settings.VERSION, "status": "operational"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check with available sources"""

    available = [
        "openalex",
        "semantic_scholar",
        "arxiv",
        "openreview",
        "crossref",
        "dblp",
        "springer",
    ]

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
        available_sources=available,
    )


@app.post("/search", response_model=SearchResponse)
async def search_papers(request: SearchRequest):
    """
    Search and rank papers from multiple sources with full metadata.
    """
    CONFIDENCE_THRESHOLD = 0.50
    PREFETCH_K = max(request.top_k * 3, 30)

    start_time = time.time()

    try:
        print("\n" + "=" * 60)
        print(f"🔎 Query:  {request.query}")
        print(f"📚 Sources:  {', '.join(request.sources)}")
        print(f"📅 Years: {request.min_year}-{request.max_year}")
        print("=" * 60 + "\n")

        # Signature now includes query to prevent cache collisions
        req_sig = signature_for_request(
            request.query,
            request.sources,
            request.min_year or 2015,
            request.max_year or 2025,
        )
        cache_sig = load_signature()

        # Always embed query once
        query_emb = embedding_service.encode_query(request.query)

        cache_results = []
        cache_best_score = None

        # 1) Cache pre-search (fast) if cache exists and matches filters
        if (
            request.use_cache
            and vector_store is not None
            and vector_store.index is not None
            and vector_store.index.ntotal > 0
            and cache_sig is not None
            and signature_matches(cache_sig, req_sig)
        ):
            cache_results = vector_store.search(query_emb, top_k=PREFETCH_K)
            if cache_results:
                cache_best_score = getattr(cache_results[0], "similarity_score", None)

            print(
                f"🧠 Cache presearch: {len(cache_results)} results, best_score={cache_best_score}"
            )

            # 2) If cache is confident, return immediately
            if (
                cache_best_score is not None
                and cache_best_score >= CONFIDENCE_THRESHOLD
            ):
                ranked_papers = dedup_ranked_papers(cache_results, request.top_k)
                processing_time = time.time() - start_time
                print(
                    f"⚡ Cache confident: returned {len(ranked_papers)} in {processing_time:.2f}s"
                )

                return SearchResponse(
                    query=request.query,
                    total_fetched=0,
                    total_returned=len(ranked_papers),
                    papers=ranked_papers,
                    processing_time_seconds=processing_time,
                    sources_used=request.sources,
                    cache_hit=True,
                )

        # 3) Cold cache OR low-confidence -> fetch fresh papers
        papers = await fetcher.fetch_papers_async(
            query=request.query,
            sources=request.sources,
            max_results=settings.MAX_PAPERS_PER_SOURCE,
            min_year=request.min_year or 2015,
            max_year=request.max_year or 2025,
            per_source_timeout_s=float(settings.FETCH_SOURCE_TIMEOUT_S),
        )

        if not papers:
            # If fetch found nothing but cache had something, return cache
            if cache_results:
                ranked_papers = dedup_ranked_papers(cache_results, request.top_k)
                processing_time = time.time() - start_time
                return SearchResponse(
                    query=request.query,
                    total_fetched=0,
                    total_returned=len(ranked_papers),
                    papers=ranked_papers,
                    processing_time_seconds=processing_time,
                    sources_used=request.sources,
                    cache_hit=True,
                )

            return SearchResponse(
                query=request.query,
                total_fetched=0,
                total_returned=0,
                papers=[],
                processing_time_seconds=time.time() - start_time,
                sources_used=request.sources,
                cache_hit=False,
            )

        # 4) Update FAISS with newly fetched papers, then search again
        if vector_store is not None:
            paper_texts = [ranker._create_paper_text(p) for p in papers]
            paper_embeddings = embedding_service.encode_documents(paper_texts)

            vector_store.add_papers(papers, paper_embeddings)
            vector_store.save()
            save_signature(req_sig)

            ranked_papers = vector_store.search(query_emb, top_k=PREFETCH_K)
            ranked_papers = dedup_ranked_papers(ranked_papers, request.top_k)
        else:
            ranked_papers = ranker.rank_papers(request.query, papers, request.top_k)
            ranked_papers = dedup_ranked_papers(ranked_papers, request.top_k)

        processing_time = time.time() - start_time

        print(f"\n{'=' * 60}")
        print(f"✅ Search completed in {processing_time:.2f}s")
        print(f"📊 Returned {len(ranked_papers)} papers")
        print(f"{'=' * 60}\n")

        return SearchResponse(
            query=request.query,
            total_fetched=len(papers),
            total_returned=len(ranked_papers),
            papers=ranked_papers,
            processing_time_seconds=processing_time,
            sources_used=request.sources,
            cache_hit=False,
        )

    except Exception as e:
        print("\n❌ Error:\n")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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
            coverage="250M+ papers",
        ),
        SourceInfo(
            id="semantic_scholar",
            name="Semantic Scholar",
            requires_api_key=False,
            status="available",
            description="AI-powered research tool with 200M+ papers",
            coverage="200M+ papers",
        ),
        SourceInfo(
            id="arxiv",
            name="ArXiv",
            requires_api_key=False,
            status="available",
            description="Preprint repository for CS, Physics, Math",
            coverage="2M+ papers",
        ),
        SourceInfo(
            id="openreview",
            name="OpenReview",
            requires_api_key=False,
            status="available",
            description="ML conferences with peer reviews",
            coverage="100K+ papers",
        ),
        SourceInfo(
            id="crossref",
            name="CrossRef",
            requires_api_key=False,
            status="available",
            description="DOI metadata for scholarly content",
            coverage="140M+ records",
        ),
        SourceInfo(
            id="dblp",
            name="DBLP",
            requires_api_key=False,
            status="available",
            description="Computer Science bibliography",
            coverage="6M+ publications",
        ),
    ]

    # IEEE
    if settings.IEEE_API_KEY:
        sources.append(
            SourceInfo(
                id="ieee",
                name="IEEE Xplore",
                requires_api_key=True,
                status="available",
                description="Engineering and CS publications",
                coverage="5M+ documents",
            )
        )
    else:
        sources.append(
            SourceInfo(
                id="ieee",
                name="IEEE Xplore",
                requires_api_key=True,
                status="unavailable",
                message="Requires IEEE_API_KEY.  Get free key at https://developer.ieee.org/",
                coverage="5M+ documents",
            )
        )

    # Springer
    if settings.SPRINGER_API_KEY:
        sources.append(
            SourceInfo(
                id="springer",
                name="Springer Nature",
                requires_api_key=True,
                status="available",
                description="Scientific, technical, and medical content",
                coverage="13M+ documents",
            )
        )
    else:
        sources.append(
            SourceInfo(
                id="springer",
                name="Springer Nature",
                requires_api_key=True,
                status="unavailable",
                message="Requires SPRINGER_API_KEY. Get free key at https://dev.springernature.com/",
                coverage="13M+ documents",
            )
        )

    return sources


@app.get("/stats")
async def get_stats():
    """System statistics"""
    return {
        "module": "crawler",
        "version": settings.VERSION,
        "embedding_model": settings.EMBEDDING_MODEL,
        "device": settings.DEVICE,
        "max_papers_per_source": settings.MAX_PAPERS_PER_SOURCE,
        "supported_sources": 10,
    }


@app.get("/debug/config")
async def debug_config():
    """Debug endpoint to check configuration"""
    return {
        "springer_key_exists": bool(settings.SPRINGER_API_KEY),
        "springer_key_length": len(settings.SPRINGER_API_KEY)
        if settings.SPRINGER_API_KEY
        else 0,
        "springer_key_preview": settings.SPRINGER_API_KEY[:10] + "..."
        if settings.SPRINGER_API_KEY and len(settings.SPRINGER_API_KEY) > 10
        else "NOT SET",
        "ieee_key_exists": bool(settings.IEEE_API_KEY)
        if hasattr(settings, "IEEE_API_KEY")
        else False,
        "device": settings.DEVICE,
        "embedding_model": settings.EMBEDDING_MODEL,
    }