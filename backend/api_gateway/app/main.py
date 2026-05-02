import sys
import io

# Fix Windows terminal encoding — prevents crash on emoji print() statements
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

# Load .env before any module imports that need env vars
load_dotenv(backend_path / ".env")

from crawler.app.main  import app as crawler_app
from crawler.app.main  import startup_event as crawler_startup
from analyzer.app.main import app as analyzer_app
from analyzer.app.main import startup as analyzer_startup
from summarization.app.main import app as summarization_app
from summarization.app.main import startup_event as summarization_startup
from auth.main import app as auth_app
from history.main import app as history_app
from shared.database import init_db

app = FastAPI(
    title="Research Platform API",
    version="2.0.0",
    description="Unified API for research paper discovery, summarization, analysis, and user management"
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

    # Initialize database tables
    init_db()
    print("INFO: Database initialized")

    await crawler_startup()
    await analyzer_startup()
    await summarization_startup()
    print("INFO: Auth module ready")
    print("INFO: History module ready")
    print("API Gateway Ready\n")

app.mount("/api/auth",          auth_app)
app.mount("/api/history",       history_app)
app.mount("/api/crawler",       crawler_app)
app.mount("/api/analyzer",      analyzer_app)
app.mount("/api/summarization", summarization_app)

@app.get("/")
async def root():
    return {
        "message": "Research Platform API Gateway",
        "version": "2.0.0",
        "modules": {
            "auth": {
                "path": "/api/auth",
                "status": "operational",
                "endpoints": {
                    "register": "/api/auth/register",
                    "login":    "/api/auth/login",
                    "profile":  "/api/auth/profile",
                    "health":   "/api/auth/health"
                }
            },
            "history": {
                "path": "/api/history",
                "status": "operational",
                "endpoints": {
                    "dashboard": "/api/history/dashboard/stats",
                    "summaries": "/api/history/summaries",
                    "searches":  "/api/history/searches",
                    "uploads":   "/api/history/uploads",
                    "health":    "/api/history/health"
                }
            },
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
            },
            "summarization": {
                "path": "/api/summarization",
                "status": "operational",
                "endpoints": {
                    "health":     "/api/summarization/health",
                    "summarize":  "/api/summarization/summarize_file",
                    "translate":  "/api/summarization/translate_and_summarize_file"
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
            "auth":           "operational",
            "history":        "operational",
            "crawler":        "operational",
            "analyzer":       "operational",
            "summarization":  "operational"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_gateway.app.main:app", host="0.0.0.0", port=8000, reload=True)