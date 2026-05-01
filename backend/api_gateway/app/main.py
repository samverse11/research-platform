from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from crawler.app.main  import app as crawler_app
from crawler.app.main  import startup_event as crawler_startup
from analyzer.app.main import app as analyzer_app          # ← ADD
from analyzer.app.main import startup as analyzer_startup  # ← ADD
from summarization.app.main import app as summarization_app
from summarization.app.main import startup_event as summarization_startup
app = FastAPI(
    title="Research Platform API",
    version="1.0.0",
    description="Unified API for research paper discovery, summarization, and analysis"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    print("\nStarting API Gateway...")
    await crawler_startup()
    await analyzer_startup()    # ← ADD
    await summarization_startup()
    print("API Gateway Ready\n")

app.mount("/api/crawler",  crawler_app)
app.mount("/api/analyzer", analyzer_app)   # ← ADD
app.mount("/api/summarization", summarization_app)
@app.get("/")
async def root():
    return {
        "message": "Research Platform API Gateway",
        "version": "1.0.0",
        "modules": {
            "crawler": {
                "path": "/api/crawler",
                "status": "operational",
                "endpoints": {
                    "health":  "/api/crawler/health",
                    "search":  "/api/crawler/search",
                    "sources": "/api/crawler/sources",
                    "stats":   "/api/crawler/stats"
                }
            },
            "analyzer": {
                "path": "/api/analyzer",
                "status": "operational",
                "endpoints": {
                    "health":  "/api/analyzer/health",
                    "analyze": "/api/analyzer/analyze"
                }
            }
        },
        "documentation": "/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "gateway": "operational",
        "modules": {
            "crawler":  "operational",
            "analyzer": "operational"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_gateway.app.main:app", host="0.0.0.0", port=8000, reload=True)