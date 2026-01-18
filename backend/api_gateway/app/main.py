# backend/api_gateway/app/main.py
from fastapi import FastAPI
from fastapi.middleware. cors import CORSMiddleware
import sys
from pathlib import Path

# Add backend modules to path
backend_path = Path(__file__).parent.parent.parent
sys.path. insert(0, str(backend_path))

# Import crawler app
from crawler.app.main import app as crawler_app

# ✅ Import startup function
from crawler.app.main import startup_event as crawler_startup

# Create main API Gateway
app = FastAPI(
    title="Research Platform API",
    version="1.0.0",
    description="Unified API for research paper discovery, summarization, and analysis"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Add startup event to call crawler's startup
@app.on_event("startup")
async def startup():
    """Initialize all modules"""
    print("\n🚀 Starting API Gateway...")
    
    # Call crawler's startup
    await crawler_startup()
    
    print("✅ API Gateway Ready\n")

# Mount sub-applications
app.mount("/api/crawler", crawler_app)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Research Platform API Gateway",
        "version": "1.0.0",
        "modules": {
            "crawler":  {
                "path": "/api/crawler",
                "status":  "operational",
                "endpoints":  {
                    "health": "/api/crawler/health",
                    "search": "/api/crawler/search",
                    "sources": "/api/crawler/sources",
                    "stats": "/api/crawler/stats"
                }
            }
        },
        "documentation": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check for all modules"""
    return {
        "status": "healthy",
        "gateway": "operational",
        "modules": {
            "crawler":  "operational"
        }
    }

if __name__ == "__main__": 
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)